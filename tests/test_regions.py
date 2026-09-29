"""Per-neuron neuropil tables and the region meshes/statistics built from them."""

import numpy as np
import pytest

from fly_brain_sim.viz import regions
from tests.conftest import scalar


def test_neuron_neuropils_add_up_to_connections(db):
    got = db.execute(
        "select sum(input_synapses), sum(output_synapses) from neuron_neuropils"
    ).fetchone()
    total = scalar(db, "select sum(syn_count) from connections_no_threshold")
    assert got == (total, total)


def test_home_neuropil_is_unique_and_the_largest(db):
    assert scalar(db, "select count(*) - count(distinct root_id) from neuron_home_neuropil") == 0
    assert (
        scalar(db, "select count(*) from neuron_home_neuropil where home_share not between 0 and 1")
        == 0
    )
    bigger = scalar(
        db,
        """
        select count(*) from neuron_home_neuropil h join neuron_neuropils p using (root_id)
        where p.neuropil not in (h.home_neuropil, 'UNASGD')
          and p.input_synapses + p.output_synapses > (
              select q.input_synapses + q.output_synapses from neuron_neuropils q
              where q.root_id = h.root_id and q.neuropil = h.home_neuropil)
        """,
    )
    assert bigger == 0


@pytest.fixture(scope="module")
def built():
    if not (regions.REGIONS_DIR / "meta.json").exists():
        pytest.skip("regions not built (scripts/build_regions.py)")
    return regions.load()


def test_every_neuropil_has_a_mesh(built, db):
    names = {r["name"] for r in built["meta"]["regions"]}
    expected = {
        r[0]
        for r in db.execute(
            "select distinct neuropil from connections where neuropil <> 'UNASGD'"
        ).fetchall()
    }
    assert names == expected and len(names) == 78
    for r in built["meta"]["regions"]:
        assert r["vertex_count"] > 0 and r["index_count"] > 0, r["name"]


def test_triangles_stay_inside_their_region(built):
    for r in built["meta"]["regions"]:
        idx = built["indices"].reshape(-1)[r["index_offset"] : r["index_offset"] + r["index_count"]]
        assert idx.min() >= r["vertex_offset"]
        assert idx.max() < r["vertex_offset"] + r["vertex_count"], r["name"]


def test_region_centroid_lies_within_its_mesh_bounds(built):
    for r in built["meta"]["regions"]:
        v = built["vertices"][r["vertex_offset"] : r["vertex_offset"] + r["vertex_count"]]
        c = np.array(r["centroid_nm"])
        assert (c >= v.min(axis=0)).all() and (c <= v.max(axis=0)).all(), r["name"]


def test_flows_follow_known_pathways(built):
    by = {r["name"]: r for r in built["meta"]["regions"]}

    def targets(name: str, n: int = 3) -> list[str]:
        return [f["region"] for f in by[name]["flows_out"][:n]]

    # Olfaction: antennal lobe projection neurons feed the lateral horn and calyx.
    assert {"LH_R", "MB_CA_R"} <= set(targets("AL_R"))
    # Mushroom body: calyx input leaves through the lobes.
    assert targets("MB_CA_R", 1) == ["MB_ML_R"]
    # Vision: medulla output goes mainly to the lobula.
    assert targets("ME_R", 1) == ["LO_R"]
    # Compass neurons dominate the ellipsoid body.
    assert by["EB"]["top_cell_types"][0]["cell_type"] == "EPG"
