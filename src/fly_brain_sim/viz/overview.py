"""Whole-brain overview: every neuron's skeleton, simplified, in a few flat buffers.

Written to data/processed/overview/ (each file also gzipped for serving):

    root_ids.i64      (n_neurons,)       neuron order; same as `neurons` ordered by root_id
    offsets.u32       (n_neurons + 1,)   first vertex of each neuron
    positions.u16     (n_vertices, 3)    x, y, z in units of UNIT_NM
    parent_delta.u32  (n_vertices,)      vertex index minus its parent's; 0 for roots
    meta.json                            counts, units, bounding box, parameters

Vertices are grouped by neuron, parents before children, so parent deltas are
mostly 1 and compress well. The client rebuilds line segments and per-vertex
neuron indices from these.
"""

import gzip
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import duckdb
import numpy as np

from fly_brain_sim.data.paths import DB_PATH, OVERVIEW_DIR
from fly_brain_sim.data.skeletons import SKELETON_ZIP, SkeletonZip, resample

UNIT_NM = 16  # uint16 * 16 nm covers ~1 mm, the whole FAFB volume
STEP_NM = 20_000
MIN_TWIG_NM = 20_000
CHUNK = 1000

_zip: SkeletonZip | None = None


def _init_worker(path: str) -> None:
    global _zip
    _zip = SkeletonZip(Path(path))


def _simplify_chunk(args):
    root_ids, step, min_twig = args
    out = []
    for rid in root_ids:
        sk = _zip.read(rid)
        kept, parent = resample(sk, step, min_twig)
        out.append((sk.xyz[kept], parent, len(sk)))
    return out


def neuron_order(db_path: Path = DB_PATH) -> np.ndarray:
    with duckdb.connect(db_path, read_only=True) as con:
        return np.array(
            [r[0] for r in con.execute("select root_id from neurons order by root_id").fetchall()],
            dtype=np.int64,
        )


def build(
    out_dir: Path = OVERVIEW_DIR,
    zip_path: Path = SKELETON_ZIP,
    db_path: Path = DB_PATH,
    step: float = STEP_NM,
    min_twig: float = MIN_TWIG_NM,
    workers: int | None = None,
    log=print,
) -> dict:
    root_ids = neuron_order(db_path)
    available = set(SkeletonZip(zip_path).root_ids)
    missing = [int(r) for r in root_ids if int(r) not in available]
    if missing:
        raise SystemExit(f"{len(missing)} neurons have no skeleton, e.g. {missing[:3]}")

    t0 = time.perf_counter()
    chunks = [
        ([int(r) for r in root_ids[i : i + CHUNK]], step, min_twig)
        for i in range(0, len(root_ids), CHUNK)
    ]
    results = []
    with ProcessPoolExecutor(workers, initializer=_init_worker, initargs=(str(zip_path),)) as ex:
        for i, res in enumerate(ex.map(_simplify_chunk, chunks)):
            results.extend(res)
            if (i + 1) % 20 == 0 or i + 1 == len(chunks):
                log(f"  {len(results):,}/{len(root_ids):,} neurons")

    counts = np.array([len(p) for _, p, _ in results], dtype=np.int64)
    offsets = np.zeros(len(counts) + 1, dtype=np.int64)
    np.cumsum(counts, out=offsets[1:])
    xyz = np.concatenate([x for x, _, _ in results])
    local_parent = np.concatenate([p for _, p, _ in results]).astype(np.int64)
    vertex = np.arange(len(xyz), dtype=np.int64)
    local = vertex - np.repeat(offsets[:-1], counts)
    parent_delta = np.where(local_parent >= 0, local - local_parent, 0)
    assert (parent_delta >= 0).all(), "parents must precede children"

    q = np.rint(xyz / UNIT_NM)
    if q.min() < 0 or q.max() > np.iinfo(np.uint16).max:
        raise ValueError(f"positions outside uint16 range: {q.min()}..{q.max()}")

    arrays = {
        "root_ids.i64": root_ids.astype("<i8"),
        "offsets.u32": offsets.astype("<u4"),
        "positions.u16": q.astype("<u2"),
        "parent_delta.u32": parent_delta.astype("<u4"),
    }
    meta = {
        "n_neurons": len(root_ids),
        "n_vertices": int(len(xyz)),
        "n_edges": int((parent_delta > 0).sum()),
        "n_source_nodes": int(sum(n for _, _, n in results)),
        "unit_nm": UNIT_NM,
        "step_nm": step,
        "min_twig_nm": min_twig,
        "bbox_nm": {
            "min": [float(v) for v in xyz.min(axis=0)],
            "max": [float(v) for v in xyz.max(axis=0)],
        },
        "files": {},
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, arr in arrays.items():
        raw = arr.tobytes()
        _write(out_dir / name, raw)
        _write(out_dir / f"{name}.gz", gzip.compress(raw, compresslevel=6, mtime=0))
        meta["files"][name] = {
            "bytes": len(raw),
            "gzip_bytes": (out_dir / f"{name}.gz").stat().st_size,
        }
    _write(out_dir / "meta.json", json.dumps(meta, indent=2).encode())
    log(f"  done in {time.perf_counter() - t0:.0f}s")
    return meta


def _write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def load(out_dir: Path = OVERVIEW_DIR) -> dict[str, np.ndarray]:
    """Read the overview buffers back (used by the API and tests)."""
    meta = json.loads((out_dir / "meta.json").read_text())
    dtypes = {"i64": "<i8", "u32": "<u4", "u16": "<u2"}
    out = {"meta": meta}
    for name in meta["files"]:
        arr = np.fromfile(out_dir / name, dtype=dtypes[name.rsplit(".", 1)[1]])
        out[name.split(".")[0]] = arr.reshape(-1, 3) if name == "positions.u16" else arr
    return out
