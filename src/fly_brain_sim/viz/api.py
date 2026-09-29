"""HTTP API for the connectome viewer.

Root IDs are always sent as strings: JavaScript numbers are float64, so an
18-digit ID sent as a JSON number would arrive as a different ID. Neurons are
also referred to by their *index*, their position in the overview buffers
(neurons ordered by root_id), which the client uses for colouring and picking.

Binary responses are little-endian, laid out as documented on each endpoint.
"""

import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import duckdb
import numpy as np
import polars as pl
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from fly_brain_sim.data.paths import DB_PATH, OVERVIEW_DIR, REPO_ROOT, SYNAPSES_DB_PATH
from fly_brain_sim.data.skeletons import SKELETON_ZIP, SkeletonZip
from fly_brain_sim.viz import overview, regions

WEB_DIST = REPO_ROOT / "web" / "dist"

# Per-neuron categorical fields the client can colour by.
COLOR_FIELDS = [
    "super_class",
    "home_neuropil",
    "flow",
    "class",
    "sub_class",
    "nt_type",
    "side",
    "ito_lee_hemilineage",
    "neuropil_group",
    "cell_type",
]
OVERVIEW_FILES = ["offsets.u32", "positions.u16", "parent_delta.u32"]
REGION_FILES = ["vertices.f32", "indices.u32"]

# One neuron per (cell type, side): the one whose synapse count is closest to the
# group's median. Used for the uncluttered "sketch" view.
REPRESENTATIVES_SQL = """
    with total as (
        select root_id, sum(input_synapses + output_synapses) as syn
        from neuron_neuropils group by 1
    ),
    typed as (
        select n.root_id, n.cell_type, n.side, coalesce(t.syn, 0) as syn
        from neurons n left join total t using (root_id)
        where n.cell_type is not null
    ),
    with_median as (
        select *, median(syn) over (partition by cell_type, side) as median_syn from typed
    ),
    ranked as (
        select root_id, row_number() over (
            partition by cell_type, side order by abs(syn - median_syn), root_id
        ) as rank
        from with_median
    )
    select root_id from ranked where rank = 1 order by root_id
"""
NEURON_SUMMARY = "name, cell_type, super_class, side, nt_type"


class State:
    def __init__(
        self,
        db_path: Path,
        synapses_path: Path,
        overview_dir: Path,
        zip_path: Path,
        regions_dir: Path,
    ):
        self.db = duckdb.connect(db_path, read_only=True)
        self.db.execute("set enable_progress_bar = false")
        self.synapses = None
        if synapses_path.exists():
            self.synapses = duckdb.connect(synapses_path, read_only=True)
            self.synapses.execute("set enable_progress_bar = false")
        self.overview_dir = overview_dir
        self.overview_meta = overview.load(overview_dir)["meta"]
        self.root_ids = np.fromfile(overview_dir / "root_ids.i64", dtype="<i8")
        if not np.array_equal(self.root_ids, overview.neuron_order(db_path)):
            raise RuntimeError("overview is out of date with the database; rebuild it")
        self.zip_path = zip_path
        self.regions_dir = regions_dir
        self.regions_meta = None
        if (regions_dir / "meta.json").exists():
            meta = json.loads((regions_dir / "meta.json").read_text())
            meta.pop("files", None)
            self.regions_meta = meta
        self.attributes: bytes | None = None  # serialised once; the data never changes
        self._local = threading.local()

    def skeletons(self) -> SkeletonZip:
        # zipfile handles are not safe to share between request threads
        if not hasattr(self._local, "zip"):
            self._local.zip = SkeletonZip(self.zip_path)
        return self._local.zip

    def index_of(self, root_id: int) -> int:
        i = int(np.searchsorted(self.root_ids, root_id))
        if i == len(self.root_ids) or self.root_ids[i] != root_id:
            raise HTTPException(404, f"unknown neuron {root_id}")
        return i

    def indices_of(self, root_ids: np.ndarray) -> np.ndarray:
        return np.searchsorted(self.root_ids, root_ids).astype(np.uint32)


def create_app(
    db_path: Path = DB_PATH,
    synapses_path: Path = SYNAPSES_DB_PATH,
    overview_dir: Path = OVERVIEW_DIR,
    zip_path: Path = SKELETON_ZIP,
    regions_dir: Path = regions.REGIONS_DIR,
    web_dist: Path = WEB_DIST,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.s = State(db_path, synapses_path, overview_dir, zip_path, regions_dir)
        yield

    app = FastAPI(title="fly-brain-sim viewer", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)  # 9 is ~10x slower

    def st(request: Request) -> State:
        return request.app.state.s

    def rows(cur, sql: str, params=()) -> list[dict]:
        res = cur.execute(sql, params)
        cols = [d[0] for d in res.description]
        return [dict(zip(cols, r, strict=True)) for r in res.fetchall()]

    def stringify_ids(d: dict) -> dict:
        return {k: (str(v) if k.endswith("root_id") and v is not None else v) for k, v in d.items()}

    @app.get("/api/meta")
    def meta(request: Request):
        s = st(request)
        return {
            "overview": s.overview_meta,
            "color_fields": COLOR_FIELDS,
            "has_synapses": s.synapses is not None,
            "has_regions": s.regions_meta is not None,
        }

    @app.get("/api/regions")
    def regions_meta(request: Request):
        """Region list with mesh ranges and statistics (see viz/regions.py)."""
        s = st(request)
        if s.regions_meta is None:
            raise HTTPException(503, "regions not built (scripts/build_regions.py)")
        return s.regions_meta

    @app.get("/api/regions/{name}")
    def regions_file(name: str, request: Request):
        s = st(request)
        if name not in REGION_FILES or s.regions_meta is None:
            raise HTTPException(404)
        return FileResponse(
            s.regions_dir / f"{name}.gz",
            media_type="application/octet-stream",
            headers={"Content-Encoding": "gzip", "Cache-Control": "no-cache"},
        )

    @app.get("/api/overview/{name}")
    def overview_file(name: str, request: Request):
        if name not in OVERVIEW_FILES:
            raise HTTPException(404)
        return FileResponse(
            st(request).overview_dir / f"{name}.gz",
            media_type="application/octet-stream",
            headers={"Content-Encoding": "gzip", "Cache-Control": "no-cache"},
        )

    @app.get("/api/neurons/attributes")
    def attributes(request: Request):
        """Root IDs (strings) and dictionary-encoded colour fields, in overview order.

        Categories are sorted by frequency; codes index into them, -1 = missing.
        `representatives` lists the overview indices of one neuron per cell type and side.
        """
        s = st(request)
        if s.attributes is None:
            cols = ", ".join(f'"{f}"' for f in COLOR_FIELDS)
            df = pl.from_arrow(
                s.db.cursor()
                .execute(
                    f"select root_id::varchar as root_id, {cols} from neurons "
                    "left join neuron_home_neuropil using (root_id) order by root_id"
                )
                .arrow()
            )
            fields = {}
            for f in COLOR_FIELDS:
                vc = (
                    df.select(pl.col(f).drop_nulls().value_counts(sort=True))
                    .unnest(f)
                    .sort(["count", f], descending=[True, False])
                )
                categories = vc[f].to_list()
                mapping = pl.DataFrame({f: categories, "code": range(len(categories))})
                codes = df.select(f).join(mapping, on=f, how="left", maintain_order="left")
                fields[f] = {
                    "categories": categories,
                    "counts": vc["count"].to_list(),
                    "codes": codes["code"].fill_null(-1).to_list(),
                }
            reps = s.db.cursor().execute(REPRESENTATIVES_SQL).fetchnumpy()["root_id"]
            body = {
                "root_ids": df["root_id"].to_list(),
                "fields": fields,
                "representatives": s.indices_of(np.asarray(reps, dtype=np.int64)).tolist(),
            }
            s.attributes = json.dumps(body, separators=(",", ":")).encode()
        return Response(s.attributes, media_type="application/json")

    @app.get("/api/search")
    def search(request: Request, q: str = Query(min_length=1), limit: int = Query(50, le=500)):
        """Match root ID (prefix), cell type, name, hemibrain type or community label.

        Exact root ID / cell type / name matches rank first, community labels last.
        """
        s = st(request)
        cur = s.db.cursor()
        q = q.strip()
        params = {"q": q, "contains": f"%{q}%"}
        id_match = "false"
        if q.isdigit():
            id_match = "n.root_id::varchar like $prefix"
            params["prefix"] = f"{q}%"
        summary = ", ".join("n." + c.strip() for c in NEURON_SUMMARY.split(","))
        sql = f"""
            with lab as (
                select root_id, min(label) as matched_label
                from labels where label ilike $contains group by 1
            ),
            m as (
                select n.root_id, {summary}, a.hemibrain_type, lab.matched_label,
                    case when n.root_id::varchar = $q then 0
                         when lower(n.cell_type) = lower($q) then 1
                         when lower(n.name) = lower($q) then 2
                         when n.cell_type ilike $q || '%' then 3
                         when n.cell_type ilike $contains or n.name ilike $contains
                              or a.hemibrain_type ilike $contains or {id_match} then 4
                         when lab.matched_label is not null then 5
                    end as rank
                from neurons n
                left join annotations a using (root_id)
                left join lab using (root_id)
            )
            select *, count(*) over () as total from m
            where rank is not null
            order by rank, cell_type, name, root_id
            limit {limit}
        """
        found = rows(cur, sql, params)
        total = found[0]["total"] if found else 0
        results = []
        for r in found:
            r.pop("total")
            r.pop("rank")
            r["index"] = s.index_of(r["root_id"])
            results.append(stringify_ids(r))
        return {"total": total, "results": results}

    @app.get("/api/neurons/{root_id}")
    def neuron(root_id: int, request: Request):
        s = st(request)
        index = s.index_of(root_id)
        cur = s.db.cursor()
        info = rows(
            cur,
            "select * from neurons left join neuron_home_neuropil using (root_id) "
            "where root_id = ?",
            [root_id],
        )[0]
        ann = rows(cur, "select * from annotations where root_id = ?", [root_id])
        shiu = cur.execute(
            "select shiu_index from shiu_neurons where root_id = ?", [root_id]
        ).fetchone()
        degree = rows(
            cur,
            """
            select
                (select count(distinct post_root_id) from connections where pre_root_id = $id)
                    as downstream_partners,
                (select count(distinct pre_root_id) from connections where post_root_id = $id)
                    as upstream_partners,
                (select coalesce(sum(syn_count), 0) from connections_no_threshold
                    where pre_root_id = $id) as output_synapses,
                (select coalesce(sum(syn_count), 0) from connections_no_threshold
                    where post_root_id = $id) as input_synapses
            """,
            {"id": root_id},
        )[0]
        return {
            "root_id": str(root_id),
            "index": index,
            "neuron": stringify_ids(info),
            "annotations": stringify_ids(ann[0]) if ann else None,
            "shiu_index": shiu[0] if shiu else None,
            **{k: int(v) for k, v in degree.items()},
        }

    @app.get("/api/neurons/{root_id}/skeleton")
    def skeleton(root_id: int, request: Request):
        """Full-resolution skeleton.

        Layout: n (uint32), xyz (float32 n*3, nm), parent (int32 n, -1 = root),
        radius (float32 n, nm), label (uint8 n, SWC label; 1 = soma).
        """
        s = st(request)
        s.index_of(root_id)
        sk = s.skeletons().read(root_id)
        body = b"".join(
            [
                np.uint32(len(sk)).tobytes(),
                sk.xyz.astype("<f4").tobytes(),
                sk.parent.astype("<i4").tobytes(),
                sk.radius.astype("<f4").tobytes(),
                sk.label.astype("u1").tobytes(),
            ]
        )
        return Response(body, media_type="application/octet-stream")

    @app.get("/api/neurons/{root_id}/partners")
    def partners(
        root_id: int,
        request: Request,
        direction: str = Query(pattern="^(upstream|downstream)$"),
        min_syn: int = Query(5, ge=1),
    ):
        """Synaptic partners with total synapse counts over all neuropils."""
        s = st(request)
        s.index_of(root_id)
        this, other = (
            ("post_root_id", "pre_root_id")
            if direction == "upstream"
            else ("pre_root_id", "post_root_id")
        )
        found = rows(
            s.db.cursor(),
            f"""
            with p as (
                select {other} as root_id, sum(syn_count) as syn_count
                from connections_no_threshold
                where {this} = ?
                group by 1 having sum(syn_count) >= ?
            )
            select p.root_id, p.syn_count, {NEURON_SUMMARY}
            from p join neurons n using (root_id)
            order by syn_count desc, root_id
            """,
            [root_id, min_syn],
        )
        idx = s.indices_of(np.array([r["root_id"] for r in found], dtype=np.int64))
        for r, i in zip(found, idx, strict=True):
            r["index"] = int(i)
        return {
            "direction": direction,
            "min_syn": min_syn,
            "partners": [stringify_ids(r) for r in found],
        }

    @app.get("/api/neurons/{root_id}/synapses")
    def synapses(
        root_id: int,
        request: Request,
        direction: str = Query(pattern="^(outgoing|incoming)$"),
    ):
        """Synapse locations (cleft centres).

        Layout: n (uint32), xyz (float32 n*3, nm), partner index (uint32 n).
        """
        s = st(request)
        s.index_of(root_id)
        if s.synapses is None:
            raise HTTPException(503, "synapse database not built (scripts/build_synapses.py)")
        this, other = (
            ("pre_root_id", "post_root_id")
            if direction == "outgoing"
            else ("post_root_id", "pre_root_id")
        )
        res = (
            s.synapses.cursor()
            .execute(
                f"select ctr_x, ctr_y, ctr_z, {other} as partner from synapses where {this} = ?",
                [root_id],
            )
            .fetchnumpy()
        )
        n = len(res["partner"])
        xyz = np.stack([res["ctr_x"], res["ctr_y"], res["ctr_z"]], axis=1).astype("<f4")
        partner = s.indices_of(np.asarray(res["partner"], dtype=np.int64)).astype("<u4")
        body = np.uint32(n).tobytes() + xyz.tobytes() + partner.tobytes()
        return Response(body, media_type="application/octet-stream")

    if web_dist.exists():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

    return app


app = create_app()
