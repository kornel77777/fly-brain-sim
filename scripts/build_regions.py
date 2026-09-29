"""Build brain region (neuropil) meshes and statistics in data/processed/regions/.

Needs the main database (scripts/build_db.py) and the synapse database
(scripts/build_synapses.py).

Usage: uv run python scripts/build_regions.py
"""

from fly_brain_sim.viz.regions import REGIONS_DIR, build


def main() -> None:
    print(f"building {REGIONS_DIR}")
    build()


if __name__ == "__main__":
    main()
