"""Root IDs must survive loading unchanged (no float round trip)."""

import duckdb

from fly_brain_sim.data.paths import CODEX_DIR
from tests.conftest import scalar


def test_float64_would_corrupt_root_ids():
    # Why IDs are never read as floats: 18-digit IDs don't fit in 53 bits.
    root_id = 720575940596125868
    assert int(float(root_id)) != root_id


def test_every_id_column_is_bigint(db):
    rows = db.execute(
        """
        select table_name, column_name, data_type from information_schema.columns
        where column_name like '%root_id' or column_name in ('supervoxel_id', 'nucleus_id')
        """
    ).fetchall()
    assert rows
    assert [r for r in rows if r[2] != "BIGINT"] == []


def test_root_ids_match_raw_text_exactly(db):
    # Compare against the raw file read as text, so no numeric parsing is involved.
    raw = duckdb.execute(
        f"select root_id from read_csv('{CODEX_DIR / 'neurons.csv.gz'}', all_varchar=true)"
    ).fetchall()
    stored = db.execute("select root_id::varchar from neurons").fetchall()
    assert sorted(raw) == sorted(stored)


def test_root_ids_look_like_flywire_ids(db):
    # All v783 root IDs are 18 digits and share the 720575940 prefix.
    bad = scalar(
        db,
        "select count(*) from neurons "
        "where root_id not between 720575940000000000 and 720575940999999999",
    )
    assert bad == 0
