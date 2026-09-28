"""The built whole-brain overview buffers."""

import numpy as np
import pytest

from fly_brain_sim.data.paths import OVERVIEW_DIR
from fly_brain_sim.viz import overview


@pytest.fixture(scope="module")
def ov():
    if not (OVERVIEW_DIR / "meta.json").exists():
        pytest.skip("overview not built (scripts/build_overview.py)")
    return overview.load()


def test_neuron_order_matches_database(ov):
    assert np.array_equal(ov["root_ids"], overview.neuron_order())


def test_offsets_cover_all_vertices(ov):
    offsets = ov["offsets"]
    assert offsets[0] == 0
    assert offsets[-1] == len(ov["positions"]) == len(ov["parent_delta"])
    assert (np.diff(offsets.astype(np.int64)) >= 1).all()  # every neuron has a vertex


def test_one_root_per_neuron_and_parents_stay_inside_their_neuron(ov):
    offsets = ov["offsets"].astype(np.int64)
    delta = ov["parent_delta"].astype(np.int64)
    counts = np.diff(offsets)
    start = np.repeat(offsets[:-1], counts)
    vertex = np.arange(len(delta))
    assert (delta[offsets[:-1]] == 0).all()  # first vertex of each neuron is its root
    assert (delta == 0).sum() == len(counts)
    assert ((vertex - delta) >= start).all()


def test_positions_within_bounding_box(ov):
    meta = ov["meta"]
    pos_nm = ov["positions"].astype(np.float64) * meta["unit_nm"]
    lo, hi = np.array(meta["bbox_nm"]["min"]), np.array(meta["bbox_nm"]["max"])
    tol = meta["unit_nm"]
    assert (pos_nm.min(axis=0) >= lo - tol).all() and (pos_nm.max(axis=0) <= hi + tol).all()
