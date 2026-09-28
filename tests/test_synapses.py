"""The synapse table (optional download) against the connection tables."""

import duckdb
import pytest

from fly_brain_sim.data.paths import DB_PATH, SYNAPSES_DB_PATH
from tests.conftest import scalar

N_SYNAPSES = 80_215_790


@pytest.fixture(scope="module")
def syn():
    if not SYNAPSES_DB_PATH.exists():
        pytest.skip("synapse DB not built (scripts/build_synapses.py)")
    con = duckdb.connect(SYNAPSES_DB_PATH, read_only=True)
    con.execute("set enable_progress_bar = false")
    con.execute(f"attach '{DB_PATH}' as main_db (read_only)")
    yield con
    con.close()


def test_synapse_count(syn):
    assert scalar(syn, "select count(*) from synapses") == N_SYNAPSES


def test_ids_are_bigint(syn):
    types = syn.execute(
        "select data_type from information_schema.columns "
        "where table_name = 'synapses' and column_name like '%root_id'"
    ).fetchall()
    assert types == [("BIGINT",), ("BIGINT",)]


def test_every_synapse_connects_known_neurons(syn):
    for col in ("pre_root_id", "post_root_id"):
        orphans = scalar(
            syn,
            f"select count(*) from synapses s anti join main_db.neurons n on n.root_id = s.{col}",
        )
        assert orphans == 0, col


def test_synapses_add_up_to_connections(syn):
    # Codex connections = synapses grouped by (pre, post, neuropil), without autapses.
    # Synapses outside any neuropil appear as 'UNASGD' there and are checked below.
    # Every connection row is backed by exactly that many synapses. The other way
    # round, 212 synapses in 44 groups (right medulla, mostly one R7 photoreceptor,
    # 720575940623940963) are missing from the Codex connection table.
    syn.execute(
        """
        create or replace temp table s as
        select pre_root_id, post_root_id, neuropil, count(*) as syn_count
        from synapses
        where pre_root_id <> post_root_id and neuropil is not null
        group by all
        """
    )
    syn.execute(
        """
        create or replace temp table c as
        select pre_root_id, post_root_id, neuropil, syn_count
        from main_db.connections_no_threshold where neuropil <> 'UNASGD'
        """
    )
    assert scalar(syn, "select count(*) from (from c except all from s)") == 0
    groups, synapses = syn.execute(
        "select count(*), sum(syn_count) from (from s except all from c)"
    ).fetchone()
    assert (groups, synapses) == (44, 212)


def test_unassigned_synapses_match_within_one(syn):
    from_synapses = scalar(
        syn,
        "select count(*) from synapses where neuropil is null and pre_root_id <> post_root_id",
    )
    from_connections = scalar(
        syn,
        "select sum(syn_count) from main_db.connections_no_threshold where neuropil = 'UNASGD'",
    )
    assert abs(from_synapses - from_connections) <= 1
