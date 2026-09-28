"""Build data/processed/flywire_783.duckdb from scratch.

Any existing database is replaced. The new one is written to a temporary file
and moved into place only when every table has been built.

Usage: uv run python scripts/build_db.py
"""

import time

from fly_brain_sim.data.build import build
from fly_brain_sim.data.paths import DB_PATH


def main() -> None:
    t0 = time.perf_counter()
    print(f"building {DB_PATH}")
    build(DB_PATH)
    size = DB_PATH.stat().st_size / 1e6
    print(f"done in {time.perf_counter() - t0:.0f}s ({size:,.0f} MB)")


if __name__ == "__main__":
    main()
