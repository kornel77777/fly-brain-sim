"""Build data/processed/synapses_783.duckdb from the Codex synapse table (~2 min).

Usage: uv run python scripts/build_synapses.py
"""

import time

from fly_brain_sim.data.paths import SYNAPSES_DB_PATH
from fly_brain_sim.data.synapses import build


def main() -> None:
    t0 = time.perf_counter()
    print(f"building {SYNAPSES_DB_PATH}")
    rows = build()
    size = SYNAPSES_DB_PATH.stat().st_size / 1e6
    print(f"done: {rows:,} synapses in {time.perf_counter() - t0:.0f}s ({size:,.0f} MB)")


if __name__ == "__main__":
    main()
