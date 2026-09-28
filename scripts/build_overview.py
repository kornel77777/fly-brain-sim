"""Build the simplified whole-brain skeleton buffers in data/processed/overview/.

Needs the main database (scripts/build_db.py) and the skeleton zip
(scripts/import_codex.py).

Usage: uv run python scripts/build_overview.py
"""

from fly_brain_sim.data.paths import OVERVIEW_DIR
from fly_brain_sim.viz.overview import build


def main() -> None:
    print(f"building {OVERVIEW_DIR}")
    meta = build()
    gz = sum(f["gzip_bytes"] for f in meta["files"].values()) / 1e6
    print(
        f"{meta['n_neurons']:,} neurons, {meta['n_source_nodes']:,} skeleton nodes -> "
        f"{meta['n_vertices']:,} vertices ({gz:.1f} MB gzipped)"
    )


if __name__ == "__main__":
    main()
