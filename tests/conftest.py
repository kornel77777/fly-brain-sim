import duckdb
import pytest

from fly_brain_sim.data.paths import DB_PATH


@pytest.fixture(scope="session")
def db():
    if not DB_PATH.exists():
        pytest.fail(f"{DB_PATH} not found; run `uv run python scripts/build_db.py` first")
    con = duckdb.connect(DB_PATH, read_only=True)
    con.execute("set enable_progress_bar = false")
    yield con
    con.close()


def scalar(con, sql: str):
    return con.execute(sql).fetchone()[0]
