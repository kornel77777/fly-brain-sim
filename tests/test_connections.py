"""Codex connection tables.

The Codex figure of 3,732,460 connections counts neuron *pairs* with >= 5
synapses. The thresholded file has one row per (pre, post, neuropil), so a pair
that spans several neuropils has several rows and the file has more rows
(5,342,446) than connections.
"""

import pytest

from tests.conftest import scalar

CODEX_CONNECTIONS = 3_732_460  # official Codex count of thresholded connections (pairs)
CODEX_CONNECTION_ROWS = 5_342_446  # rows in the thresholded file (split by neuropil)
THRESHOLD = 5

TABLES = ["connections", "connections_no_threshold"]


def test_thresholded_pair_count_matches_codex(db):
    pairs = scalar(
        db, "select count(*) from (select distinct pre_root_id, post_root_id from connections)"
    )
    assert pairs == CODEX_CONNECTIONS


def test_thresholded_rows_are_split_by_neuropil(db):
    rows = scalar(db, "select count(*) from connections")
    unique = scalar(
        db,
        "select count(*) from "
        "(select distinct pre_root_id, post_root_id, neuropil from connections)",
    )
    assert rows == unique == CODEX_CONNECTION_ROWS


def test_threshold_applies_to_pair_totals(db):
    smallest = scalar(
        db,
        "select min(s) from (select sum(syn_count) s from connections "
        "group by pre_root_id, post_root_id)",
    )
    assert smallest >= THRESHOLD


def test_thresholded_is_subset_of_unthresholded(db):
    # Every pair with >= 5 synapses in the full table, and nothing else.
    diff = scalar(
        db,
        f"""
        with strong as (
            select pre_root_id, post_root_id from connections_no_threshold
            group by all having sum(syn_count) >= {THRESHOLD}
        ),
        expected as (
            select c.* from connections_no_threshold c
            semi join strong using (pre_root_id, post_root_id)
        )
        select (select count(*) from (from expected except all from connections))
             + (select count(*) from (from connections except all from expected))
        """,
    )
    assert diff == 0


@pytest.mark.parametrize("table", TABLES)
def test_both_endpoints_are_known_neurons(db, table):
    for col in ("pre_root_id", "post_root_id"):
        orphans = scalar(
            db, f"select count(*) from {table} c anti join neurons n on n.root_id = c.{col}"
        )
        assert orphans == 0, col


@pytest.mark.parametrize("table", TABLES)
def test_no_nulls_self_loops_or_empty_edges(db, table):
    row = db.execute(
        f"""
        select
            count(*) filter (pre_root_id is null or post_root_id is null or neuropil is null
                             or syn_count is null or nt_type is null),
            count(*) filter (pre_root_id = post_root_id),
            count(*) filter (syn_count < 1)
        from {table}
        """
    ).fetchone()
    assert row == (0, 0, 0)
