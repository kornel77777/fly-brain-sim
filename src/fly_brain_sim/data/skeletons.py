"""Neuron skeletons from the Codex "LOD1 healed" zip (one <root_id>.swc per neuron).

Files are read straight from the zip, which avoids unpacking 33.5 GB. SWC
columns are: node id, label, x, y, z, radius, parent id (-1 for the root), with
positions and radii in nm. Node ids are 1..N in every file, which is checked.
"""

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numba
import numpy as np
import polars as pl

from fly_brain_sim.data.codex import SKELETONS
from fly_brain_sim.data.paths import CODEX_DIR

SKELETON_ZIP = CODEX_DIR / SKELETONS

SWC_SCHEMA = {
    "node": pl.Int32,
    "label": pl.Int8,
    "x": pl.Float32,
    "y": pl.Float32,
    "z": pl.Float32,
    "radius": pl.Float32,
    "parent": pl.Int32,
}


@dataclass
class Skeleton:
    root_id: int
    xyz: np.ndarray  # (n, 3) float32, nm
    parent: np.ndarray  # (n,) int32, 0-based index of the parent node, -1 for roots
    radius: np.ndarray  # (n,) float32, nm
    label: np.ndarray  # (n,) int8, SWC label (1 = soma)

    def __len__(self) -> int:
        return len(self.parent)


def parse_swc(data: bytes, root_id: int) -> Skeleton:
    df = pl.read_csv(
        io.BytesIO(data), separator=" ", comment_prefix="#", has_header=False, schema=SWC_SCHEMA
    )
    node = df["node"].to_numpy()
    if not np.array_equal(node, np.arange(1, len(node) + 1, dtype=node.dtype)):
        raise ValueError(f"{root_id}: SWC node ids are not 1..N")
    parent = df["parent"].to_numpy().copy()
    parent[parent > 0] -= 1  # 1-based ids -> 0-based indices; -1 stays -1
    return Skeleton(
        root_id=root_id,
        xyz=np.ascontiguousarray(df.select("x", "y", "z").to_numpy(), dtype=np.float32),
        parent=parent.astype(np.int32),
        radius=df["radius"].to_numpy(),
        label=df["label"].to_numpy(),
    )


class SkeletonZip:
    """Random access to skeletons in the zip. Not thread-safe; use one per thread."""

    def __init__(self, path: Path = SKELETON_ZIP):
        self.zip = zipfile.ZipFile(path)
        self.root_ids = sorted(int(n[:-4]) for n in self.zip.namelist())

    def __contains__(self, root_id: int) -> bool:
        try:
            self.zip.getinfo(f"{root_id}.swc")
        except KeyError:
            return False
        return True

    def read(self, root_id: int) -> Skeleton:
        return parse_swc(self.zip.read(f"{root_id}.swc"), root_id)

    def close(self) -> None:
        self.zip.close()


@numba.njit(cache=True)
def _topological_order(parent):
    """Node order in which every parent comes before its children (handles forests)."""
    n = len(parent)
    counts = np.zeros(n + 1, np.int64)
    for i in range(n):
        if parent[i] >= 0:
            counts[parent[i] + 1] += 1
    start = np.cumsum(counts)
    children = np.empty(max(start[-1], 1), np.int64)
    fill = start[:-1].copy()
    for i in range(n):
        p = parent[i]
        if p >= 0:
            children[fill[p]] = i
            fill[p] += 1
    order = np.empty(n, np.int64)
    k = 0
    stack = np.empty(n, np.int64)
    for r in range(n):
        if parent[r] >= 0:
            continue
        top = 0
        stack[0] = r
        top = 1
        while top > 0:
            top -= 1
            v = stack[top]
            order[k] = v
            k += 1
            for j in range(start[v], start[v + 1]):
                stack[top] = children[j]
                top += 1
    return order[:k]


@numba.njit(cache=True)
def _resample(xyz, parent, step, min_twig):
    n = len(parent)
    order = _topological_order(parent)

    edge = np.zeros(n, np.float64)  # length of the edge to the parent
    for v in range(n):
        p = parent[v]
        if p >= 0:
            d = 0.0
            for c in range(3):
                t = xyz[v, c] - xyz[p, c]
                d += t * t
            edge[v] = np.sqrt(d)

    # Longest cable path from each node down to a tip, and the child it runs through.
    height = np.zeros(n, np.float64)
    main_child = np.full(n, -1, np.int64)
    for i in range(n - 1, -1, -1):
        v = order[i]
        p = parent[v]
        if p >= 0:
            h = height[v] + edge[v]
            if main_child[p] < 0 or h > height[p]:
                height[p] = h
                main_child[p] = v

    # A side branch survives only if it is at least min_twig long; the longest
    # continuation at each branch point always survives, so tips are not eroded.
    alive = np.zeros(n, np.bool_)
    n_children = np.zeros(n, np.int64)  # among alive nodes
    for v in order:
        p = parent[v]
        if p < 0:
            alive[v] = True
        elif alive[p]:
            alive[v] = main_child[p] == v or height[v] + edge[v] >= min_twig
    for v in range(n):
        if alive[v] and parent[v] >= 0:
            n_children[parent[v]] += 1

    acc = np.zeros(n, np.float64)  # cable length since the nearest kept ancestor
    kept_anc = np.full(n, -1, np.int64)  # nearest kept ancestor (or self if kept)
    new_index = np.full(n, -1, np.int64)
    new_parent = np.full(n, -1, np.int64)
    m = 0
    for v in order:
        if not alive[v]:
            continue
        p = parent[v]
        if p < 0:
            keep = True
            anc = -1
        else:
            acc[v] = acc[p] + edge[v]
            anc = kept_anc[p]
            keep = n_children[v] != 1 or acc[v] >= step  # tips, branch points, every step
        if keep:
            new_index[v] = m
            new_parent[m] = new_index[anc] if anc >= 0 else -1
            m += 1
            acc[v] = 0.0
            kept_anc[v] = v
        else:
            kept_anc[v] = anc
    kept = np.empty(m, np.int64)
    for v in range(n):
        if new_index[v] >= 0:
            kept[new_index[v]] = v
    return kept, new_parent[:m]


def resample(
    sk: Skeleton, step: float, min_twig: float | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Coarse copy of a skeleton for overview rendering.

    First prunes side branches shorter than `min_twig` nm (default: `step`),
    measured from their branch point to their farthest tip, then keeps the root,
    the remaining tips and branch points, and one node every `step` nm of cable
    in between.
    Returns (indices of the kept nodes in `sk`, parent of each kept node as an
    index into the kept nodes, -1 for roots).
    """
    min_twig = step if min_twig is None else min_twig
    kept, parent = _resample(sk.xyz, sk.parent, float(step), float(min_twig))
    return kept, parent.astype(np.int32)
