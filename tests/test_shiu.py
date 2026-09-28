"""Shiu et al. 2024 model files versus the Codex data.

Neuron IDs correspond: every Shiu neuron is a v783 neuron. The connectivity is
*not* the same as the Codex "Princeton" connections, though: Shiu's weights come
from a different synapse table (54.5M synapses vs 76.9M), so pair weights differ
and some pairs exist in only one of the two.
"""

from tests.conftest import scalar

N_SHIU_NEURONS = 138_639
# v783 neurons absent from Completeness_783.csv, mostly sensory afferents.
N_NEURONS_NOT_IN_SHIU = 616


def test_shiu_neuron_count(db):
    assert scalar(db, "select count(*) from shiu_neurons") == N_SHIU_NEURONS
    assert scalar(db, "select count(distinct root_id) from shiu_neurons") == N_SHIU_NEURONS


def test_all_shiu_neurons_are_codex_neurons(db):
    assert scalar(db, "select count(*) from shiu_neurons anti join neurons using (root_id)") == 0


def test_codex_neurons_missing_from_shiu(db):
    missing = scalar(db, "select count(*) from neurons anti join shiu_neurons using (root_id)")
    assert missing == N_NEURONS_NOT_IN_SHIU
    sensory = scalar(
        db,
        "select count(*) from neurons anti join shiu_neurons using (root_id) "
        "where super_class like 'sensory%'",
    )
    assert sensory / missing > 0.9


def test_shiu_index_is_contiguous(db):
    lo, hi, n = db.execute(
        "select min(shiu_index), max(shiu_index), count(distinct shiu_index) from shiu_neurons"
    ).fetchone()
    assert (lo, hi, n) == (0, N_SHIU_NEURONS - 1, N_SHIU_NEURONS)


def test_connection_indices_match_ids(db):
    bad = scalar(
        db,
        """
        select count(*) from shiu_connections c
        left join shiu_neurons a on a.shiu_index = c.pre_shiu_index
        left join shiu_neurons b on b.shiu_index = c.post_shiu_index
        where a.root_id is distinct from c.pre_root_id
           or b.root_id is distinct from c.post_root_id
        """,
    )
    assert bad == 0


def test_connection_endpoints_are_codex_neurons(db):
    for col in ("pre_root_id", "post_root_id"):
        orphans = scalar(
            db,
            f"select count(*) from shiu_connections c anti join neurons n on n.root_id = c.{col}",
        )
        assert orphans == 0, col


def test_pairs_unique_and_weights_consistent(db):
    row = db.execute(
        """
        select
            count(*) - count(distinct (pre_root_id, post_root_id)),
            count(*) filter (sign not in (-1, 1)),
            count(*) filter (signed_syn_count <> sign * syn_count),
            count(*) filter (syn_count < 1)
        from shiu_connections
        """
    ).fetchone()
    assert row == (0, 0, 0, 0)


def test_sign_is_a_property_of_the_presynaptic_neuron(db):
    mixed = scalar(
        db,
        "select count(*) from (select pre_root_id from shiu_connections "
        "group by 1 having count(distinct sign) > 1)",
    )
    assert mixed == 0


def test_sign_agrees_with_codex_neurotransmitter(db):
    # The model treats GABA and glutamate as inhibitory, everything else as excitatory.
    agree, total = db.execute(
        """
        with s as (select distinct pre_root_id as root_id, sign from shiu_connections)
        select
            count(*) filter (sign = case when nt_type in ('GABA', 'GLUT') then -1 else 1 end),
            count(*)
        from s join neurons using (root_id)
        where nt_type is not null
        """
    ).fetchone()
    assert agree / total > 0.99


def test_shiu_pairs_largely_present_in_codex(db):
    # Different synapse tables, so only broad overlap is expected (~89% at build time).
    found, total = db.execute(
        """
        with codex as (
            select distinct pre_root_id, post_root_id from connections_no_threshold
        )
        select count(c.pre_root_id), count(*)
        from shiu_connections s
        left join codex c using (pre_root_id, post_root_id)
        """
    ).fetchone()
    assert found / total > 0.85
