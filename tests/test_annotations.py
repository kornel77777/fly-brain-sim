from tests.conftest import scalar


def test_annotations_cover_exactly_the_codex_neurons(db):
    assert scalar(db, "select count(*) - count(distinct root_id) from annotations") == 0
    assert scalar(db, "select count(*) from annotations anti join neurons using (root_id)") == 0
    assert scalar(db, "select count(*) from neurons anti join annotations using (root_id)") == 0


def test_super_class_mostly_agrees_with_codex(db):
    agree, total = db.execute(
        """
        select count(*) filter (a.super_class = n.super_class), count(*)
        from annotations a join neurons n using (root_id)
        """
    ).fetchone()
    assert agree / total > 0.99
