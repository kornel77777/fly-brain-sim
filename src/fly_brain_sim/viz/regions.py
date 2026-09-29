"""Brain regions (neuropils): surface meshes and summary statistics.

FlyWire assigns every synapse to one of 78 neuropils. A region's shape is taken
from where its synapses are: synapse positions are binned into VOXEL_NM voxels,
voxels with at least MIN_SYNAPSES synapses form a mask, stray specks are removed
and holes filled, and the smoothed mask is turned into a surface with marching
cubes. The result is a low-detail but faithful outline of each region.

Written to data/processed/regions/ (binary files also gzipped for serving):

    meta.json       per region: mesh ranges, synapse/neuron counts, centroid,
                    top cell types, and the regions it exchanges most signal with
    vertices.f32    (n, 3) positions in nm
    indices.u32     (m, 3) triangles, indexing into vertices

Region-to-region flow: for every neuron, its output synapses in region B are
credited to region A in proportion to the share of its input synapses in A
(A -> B means "neurons receiving input in A send output to B").
"""

import gzip
import json
import os
import time
from pathlib import Path

import duckdb
import numpy as np
from scipy import ndimage
from skimage.measure import marching_cubes

from fly_brain_sim.data.paths import DB_PATH, PROCESSED_DIR, SYNAPSES_DB_PATH

REGIONS_DIR = PROCESSED_DIR / "regions"
VOXEL_NM = 4000
MIN_SYNAPSES = 3  # per voxel
MIN_COMPONENT = 0.02  # drop blobs smaller than this share of the region's largest
SMOOTH_SIGMA = 1.0  # voxels
TOP_N = 6
UNASSIGNED = "UNASGD"


def voxel_counts(synapses_path: Path = SYNAPSES_DB_PATH) -> dict[str, np.ndarray]:
    """Per neuropil: (k, 4) int array of voxel x, y, z and synapse count."""
    with duckdb.connect(synapses_path, read_only=True) as con:
        con.execute("set enable_progress_bar = false")
        res = con.execute(
            f"""
            select neuropil,
                   (ctr_x // {VOXEL_NM})::INTEGER as vx,
                   (ctr_y // {VOXEL_NM})::INTEGER as vy,
                   (ctr_z // {VOXEL_NM})::INTEGER as vz,
                   count(*)::INTEGER as n
            from synapses where neuropil is not null
            group by all
            """
        ).fetchnumpy()
    neuropil = np.asarray(res["neuropil"], dtype=object)
    data = np.stack([res["vx"], res["vy"], res["vz"], res["n"]], axis=1)
    order = np.argsort(neuropil, kind="stable")
    neuropil, data = neuropil[order], data[order]
    names, starts = np.unique(neuropil, return_index=True)
    bounds = [*starts[1:], len(neuropil)]
    return {str(n): data[s:e] for n, s, e in zip(names, starts, bounds, strict=True)}


def region_mask(voxels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Cleaned boolean mask of a region and the voxel coordinate of its origin."""
    pad = 3
    origin = voxels[:, :3].min(axis=0) - pad
    shape = voxels[:, :3].max(axis=0) - origin + pad + 1
    counts = np.zeros(shape, dtype=np.int32)
    idx = voxels[:, :3] - origin
    counts[idx[:, 0], idx[:, 1], idx[:, 2]] = voxels[:, 3]

    mask = counts >= MIN_SYNAPSES
    labels, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum_labels(mask, labels, index=np.arange(1, n + 1))
        keep = np.flatnonzero(sizes >= MIN_COMPONENT * sizes.max()) + 1
        mask = np.isin(labels, keep)
    mask = ndimage.binary_closing(mask, iterations=2)
    mask = ndimage.binary_fill_holes(mask)
    return mask, origin


def region_mesh(voxels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Smoothed surface of a region: vertices in nm (float32), triangles (uint32)."""
    mask, origin = region_mask(voxels)
    field = ndimage.gaussian_filter(mask.astype(np.float32), SMOOTH_SIGMA)
    verts, faces, _, _ = marching_cubes(field, level=0.5)
    verts_nm = (verts + origin + 0.5) * VOXEL_NM
    return verts_nm.astype(np.float32), faces.astype(np.uint32)


def region_stats(db_path: Path = DB_PATH) -> dict[str, dict]:
    """Synapses, home neurons, top cell types and strongest flows per region."""
    with duckdb.connect(db_path, read_only=True) as con:
        con.execute("set enable_progress_bar = false")

        def rows(sql: str) -> list[tuple]:
            return con.execute(sql).fetchall()

        stats: dict[str, dict] = {}
        for np_, syn in rows(
            f"""
            select neuropil, sum(input_synapses) from neuron_neuropils
            where neuropil <> '{UNASSIGNED}' group by 1
            """
        ):
            stats[np_] = {
                "synapses": int(syn),
                "home_neurons": 0,
                "top_cell_types": [],
                "flows_in": [],
                "flows_out": [],
            }
        for np_, n in rows("select home_neuropil, count(*) from neuron_home_neuropil group by 1"):
            stats[np_]["home_neurons"] = int(n)

        for np_, cell_type, syn in rows(
            f"""
            with per_type as (
                select p.neuropil, n.cell_type,
                       sum(p.input_synapses + p.output_synapses) as syn
                from neuron_neuropils p join neurons n using (root_id)
                where p.neuropil <> '{UNASSIGNED}' and n.cell_type is not null
                group by all
            )
            select neuropil, cell_type, syn from (
                select *, row_number() over (
                    partition by neuropil order by syn desc, cell_type
                ) as rank
                from per_type
            ) where rank <= {TOP_N}
            order by neuropil, rank
            """
        ):
            stats[np_]["top_cell_types"].append({"cell_type": cell_type, "synapses": int(syn)})

        flows = rows(
            f"""
            with p as (select * from neuron_neuropils where neuropil <> '{UNASSIGNED}'),
            inputs as (
                select root_id, neuropil as src,
                       input_synapses / sum(input_synapses) over (partition by root_id) as share
                from p where input_synapses > 0
            ),
            outputs as (select root_id, neuropil as dst, output_synapses from p
                        where output_synapses > 0)
            select src, dst, sum(share * output_synapses) as flow
            from inputs join outputs using (root_id)
            where src <> dst
            group by all
            """
        )
    flows.sort(key=lambda r: -r[2])
    for src, dst, flow in flows:
        if len(stats[src]["flows_out"]) < TOP_N:
            stats[src]["flows_out"].append({"region": dst, "synapses": round(flow)})
        if len(stats[dst]["flows_in"]) < TOP_N:
            stats[dst]["flows_in"].append({"region": src, "synapses": round(flow)})
    return stats


def build(
    out_dir: Path = REGIONS_DIR,
    synapses_path: Path = SYNAPSES_DB_PATH,
    db_path: Path = DB_PATH,
    log=print,
) -> dict:
    if not synapses_path.exists():
        raise SystemExit(f"{synapses_path} not found; run scripts/build_synapses.py first")
    t0 = time.perf_counter()
    voxels = voxel_counts(synapses_path)
    log(f"  voxelised {len(voxels)} regions ({time.perf_counter() - t0:.0f}s)")
    stats = region_stats(db_path)

    regions, all_verts, all_faces = [], [], []
    n_verts = n_faces = 0
    for name in sorted(voxels):
        verts, faces = region_mesh(voxels[name])
        counts = voxels[name][:, 3].astype(np.float64)
        centroid = (voxels[name][:, :3] + 0.5).T @ counts / counts.sum() * VOXEL_NM
        regions.append(
            {
                "name": name,
                "vertex_offset": n_verts,
                "vertex_count": len(verts),
                "index_offset": n_faces * 3,
                "index_count": len(faces) * 3,
                "centroid_nm": [round(float(c)) for c in centroid],
                **stats[name],
            }
        )
        all_verts.append(verts)
        all_faces.append(faces + n_verts)
        n_verts += len(verts)
        n_faces += len(faces)

    arrays = {
        "vertices.f32": np.concatenate(all_verts).astype("<f4"),
        "indices.u32": np.concatenate(all_faces).astype("<u4"),
    }
    meta = {
        "voxel_nm": VOXEL_NM,
        "min_synapses_per_voxel": MIN_SYNAPSES,
        "n_vertices": n_verts,
        "n_triangles": n_faces,
        "regions": regions,
        "files": {},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, arr in arrays.items():
        raw = arr.tobytes()
        _write(out_dir / name, raw)
        _write(out_dir / f"{name}.gz", gzip.compress(raw, compresslevel=6, mtime=0))
        meta["files"][name] = {"bytes": len(raw)}
    _write(out_dir / "meta.json", json.dumps(meta, indent=1).encode())
    log(f"  {len(regions)} regions, {n_faces:,} triangles ({time.perf_counter() - t0:.0f}s)")
    return meta


def _write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def load(out_dir: Path = REGIONS_DIR) -> dict:
    meta = json.loads((out_dir / "meta.json").read_text())
    return {
        "meta": meta,
        "vertices": np.fromfile(out_dir / "vertices.f32", dtype="<f4").reshape(-1, 3),
        "indices": np.fromfile(out_dir / "indices.u32", dtype="<u4").reshape(-1, 3),
    }
