"""Copy manually downloaded Codex files into data/raw/codex/ under canonical names.

Each .csv.gz in the source folder is identified by its header (and, for the two
connection tables, by whether every neuron pair has >= 5 synapses), so the
browser's display names like "Neurons Data.csv.gz" don't matter.

The ~2.7 GB synapse table is symlinked rather than copied.
Existing files in data/raw/codex/ are left alone.

Usage: uv run python scripts/import_codex.py ~/Downloads/flywire
"""

import argparse
import shutil
import sys
from pathlib import Path

from fly_brain_sim.data.codex import SYNAPSE_TABLE, classify
from fly_brain_sim.data.paths import CODEX_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="folder with the Codex .csv.gz downloads")
    args = parser.parse_args()

    CODEX_DIR.mkdir(parents=True, exist_ok=True)
    seen: dict[str, Path] = {}
    for src in sorted(args.source.expanduser().glob("*.gz")):
        name = classify(src)
        if name is None:
            print(f"??     {src.name} (unrecognised header, ignored)")
            continue
        if name in seen:
            sys.exit(f"error: {src.name} and {seen[name].name} both look like {name}")
        seen[name] = src

        dest = CODEX_DIR / name
        if dest.exists() or dest.is_symlink():
            print(f"skip   {name} (already present)")
        elif name == SYNAPSE_TABLE:
            dest.symlink_to(src.resolve())
            print(f"link   {name} -> {src}")
        else:
            shutil.copy2(src, dest)
            print(f"copy   {name} <- {src.name}")


if __name__ == "__main__":
    main()
