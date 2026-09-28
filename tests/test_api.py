"""Viewer API, against the real database and overview."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from fly_brain_sim.data.paths import OVERVIEW_DIR, SYNAPSES_DB_PATH
from fly_brain_sim.data.skeletons import SKELETON_ZIP, SkeletonZip
from fly_brain_sim.viz.api import create_app
from tests.conftest import scalar

T5C = 720575940596125868  # smallest root ID, so overview index 0


@pytest.fixture(scope="module")
def client():
    if not (OVERVIEW_DIR / "meta.json").exists() or not SKELETON_ZIP.exists():
        pytest.skip("overview or skeletons missing")
    with TestClient(create_app()) as c:
        yield c


def test_meta(client):
    meta = client.get("/api/meta").json()
    assert meta["overview"]["n_neurons"] == 139_255
    assert "super_class" in meta["color_fields"]


def test_overview_files_are_served_gzipped(client):
    r = client.get("/api/overview/offsets.u32")
    assert r.headers["content-encoding"] == "gzip"
    offsets = np.frombuffer(r.content, dtype="<u4")
    assert len(offsets) == 139_256
    assert client.get("/api/overview/meta.json").status_code == 404  # only whitelisted files


def test_attributes_keep_root_ids_exact(client, db):
    body = client.get("/api/neurons/attributes").json()
    expected = [
        r[0] for r in db.execute("select root_id::varchar from neurons order by 1").fetchall()
    ]
    # varchar order equals numeric order here because all IDs have 18 digits
    assert body["root_ids"] == expected
    nt = body["fields"]["nt_type"]
    assert len(nt["codes"]) == 139_255
    assert nt["categories"][0] == "ACH"
    assert sum(nt["counts"]) == sum(c >= 0 for c in nt["codes"])


def test_search_finds_cell_types_ids_and_labels(client):
    kc = client.get("/api/search", params={"q": "KCg-m"}).json()
    assert kc["results"][0]["cell_type"] == "KCg-m"
    by_id = client.get("/api/search", params={"q": str(T5C)}).json()
    assert by_id["results"][0]["root_id"] == str(T5C)
    assert by_id["results"][0]["index"] == 0
    mn9 = client.get("/api/search", params={"q": "MN9"}).json()  # only in community labels
    assert mn9["total"] >= 1 and "MN9" in mn9["results"][0]["matched_label"]


def test_neuron_info(client, db):
    info = client.get(f"/api/neurons/{T5C}").json()
    assert info["root_id"] == str(T5C) and info["index"] == 0
    assert info["neuron"]["cell_type"] == "T5c"
    assert info["annotations"]["root_id"] == str(T5C)
    out = scalar(
        db, f"select sum(syn_count) from connections_no_threshold where pre_root_id = {T5C}"
    )
    assert info["output_synapses"] == out


def test_unknown_neuron_is_404(client):
    assert client.get("/api/neurons/720575940000000000").status_code == 404


def test_skeleton_binary_layout(client):
    body = client.get(f"/api/neurons/{T5C}/skeleton").content
    n = int(np.frombuffer(body[:4], dtype="<u4")[0])
    assert len(body) == 4 + n * (12 + 4 + 4 + 1)
    xyz = np.frombuffer(body[4 : 4 + 12 * n], dtype="<f4").reshape(n, 3)
    parent = np.frombuffer(body[4 + 12 * n : 4 + 16 * n], dtype="<i4")
    sk = SkeletonZip().read(T5C)
    assert np.array_equal(xyz, sk.xyz) and np.array_equal(parent, sk.parent)


@pytest.mark.parametrize(
    ("direction", "this", "other"),
    [("upstream", "post_root_id", "pre_root_id"), ("downstream", "pre_root_id", "post_root_id")],
)
def test_partners_match_connections(client, db, direction, this, other):
    body = client.get(
        f"/api/neurons/{T5C}/partners", params={"direction": direction, "min_syn": 1}
    ).json()
    expected = db.execute(
        f"select {other}::varchar, sum(syn_count) from connections_no_threshold "
        f"where {this} = {T5C} group by 1"
    ).fetchall()
    assert {(p["root_id"], p["syn_count"]) for p in body["partners"]} == set(expected)
    counts = [p["syn_count"] for p in body["partners"]]
    assert counts == sorted(counts, reverse=True)


def test_synapses_binary_layout(client):
    if not SYNAPSES_DB_PATH.exists():
        pytest.skip("synapse DB not built")
    body = client.get(f"/api/neurons/{T5C}/synapses", params={"direction": "outgoing"}).content
    n = int(np.frombuffer(body[:4], dtype="<u4")[0])
    assert n > 0 and len(body) == 4 + n * 16
    partner = np.frombuffer(body[4 + 12 * n :], dtype="<u4")
    assert (partner < 139_255).all()
