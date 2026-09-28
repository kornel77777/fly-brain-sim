from tests.conftest import scalar

N_NEURONS = 139_255  # proofread neurons in FlyWire v783 (Dorkenwald et al. 2024)


def test_neuron_count(db):
    assert scalar(db, "select count(*) from neurons") == N_NEURONS


def test_root_id_unique_and_not_null(db):
    assert scalar(db, "select count(distinct root_id) from neurons") == N_NEURONS
    assert scalar(db, "select count(*) from neurons where root_id is null") == 0


def test_every_neuron_has_classification_and_name(db):
    assert scalar(db, "select count(*) from neurons where super_class is null") == 0
    assert scalar(db, "select count(*) from neurons where name is null") == 0


def test_per_neuron_tables_reference_known_neurons(db):
    tables = [
        "coordinates",
        "labels",
        "processed_labels",
        "visual_neuron_types",
        "column_assignment",
        "connectivity_tags",
    ]
    for t in tables:
        orphans = scalar(db, f"select count(*) from {t} anti join neurons using (root_id)")
        assert orphans == 0, t


def test_coordinates_parsed_into_three_values(db):
    missing = scalar(
        db, "select count(*) from coordinates where x_nm is null or y_nm is null or z_nm is null"
    )
    assert missing == 0
