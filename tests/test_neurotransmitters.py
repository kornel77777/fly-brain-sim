"""Sanity checks on the neurotransmitter predictions (Eckstein et al. 2024, via Codex)."""

from tests.conftest import scalar

NT_TYPES = {"ACH", "GABA", "GLUT", "DA", "SER", "OCT"}
PROBS = ["ach_avg", "gaba_avg", "glut_avg", "da_avg", "ser_avg", "oct_avg"]
PROB_SUM = " + ".join(PROBS)


def distribution(db) -> dict[str, float]:
    rows = db.execute(
        "select nt_type, count(*) from neurons where nt_type is not null group by 1"
    ).fetchall()
    total = sum(n for _, n in rows)
    return {nt: n / total for nt, n in rows}


def test_nt_types_are_known(db):
    for table in ("neurons", "connections", "connections_no_threshold"):
        values = {r[0] for r in db.execute(f"select distinct nt_type from {table}").fetchall()}
        assert values - {None} <= NT_TYPES, table


def test_probabilities_in_range_and_sum_to_one(db):
    outside = " or ".join(f"{p} not between 0 and 1" for p in PROBS)
    out_of_range = scalar(db, f"select count(*) from neurons where {outside}")
    assert out_of_range == 0
    # Values are rounded to 2 decimals, so sums land within about +-0.02 of 1.
    lo, hi = db.execute(
        f"select min({PROB_SUM}), max({PROB_SUM}) from neurons where {PROB_SUM} > 0"
    ).fetchone()
    assert 0.97 <= lo and hi <= 1.03


def test_nt_type_is_the_most_likely_transmitter(db):
    bad = scalar(
        db,
        f"""
        select count(*) from neurons
        where nt_type is not null and (
            nt_type_score <> greatest({", ".join(PROBS)})
            or nt_type <> case greatest({", ".join(PROBS)})
                when ach_avg then 'ACH' when gaba_avg then 'GABA' when glut_avg then 'GLUT'
                when da_avg then 'DA' when ser_avg then 'SER' when oct_avg then 'OCT' end
        )
        """,
    )
    assert bad == 0


def test_unassigned_neurons_have_low_confidence(db):
    # Neurons without an nt_type have either no prediction at all or a weak one.
    top = scalar(db, f"select max(greatest({', '.join(PROBS)})) from neurons where nt_type is null")
    assert top < 0.6


def test_distribution_is_plausible(db):
    d = distribution(db)
    assert max(d, key=d.get) == "ACH"
    assert 0.60 < d["ACH"] < 0.75
    assert 0.20 < d["GABA"] + d["GLUT"] < 0.35
    assert d["DA"] + d["SER"] + d["OCT"] < 0.03
    missing = scalar(db, "select avg((nt_type is null)::int) from neurons")
    assert missing < 0.2


def test_connection_nt_matches_presynaptic_neuron(db):
    mismatched = scalar(
        db,
        """
        select count(*) from connections c join neurons n on n.root_id = c.pre_root_id
        where n.nt_type is not null and c.nt_type <> n.nt_type
        """,
    )
    assert mismatched == 0


def test_annotation_top_nt_values_are_known(db):
    values = {r[0] for r in db.execute("select distinct top_nt from annotations").fetchall()}
    expected = {"acetylcholine", "gaba", "glutamate", "dopamine", "serotonin", "octopamine"}
    assert values - {None} <= expected
