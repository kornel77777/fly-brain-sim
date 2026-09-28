"""Download the external GitHub files into data/raw/external/.

Safe to re-run: files that already exist with the expected size are skipped.
Downloads go to a temporary file first, so an interrupted run never leaves a
half-written file behind.

Usage: uv run python scripts/fetch_external.py
"""

import shutil
import sys
import urllib.request

from fly_brain_sim.data.external import EXTERNAL_FILES
from fly_brain_sim.data.paths import EXTERNAL_DIR


def fetch(f, dest_dir=EXTERNAL_DIR) -> None:
    dest = dest_dir / f.filename
    if dest.exists():
        size = dest.stat().st_size
        if size == f.size:
            print(f"skip   {dest.name} (already present)")
            return
        sys.exit(
            f"error: {dest} exists but is {size} bytes, expected {f.size}. Delete it and run again."
        )

    print(f"fetch  {dest.name} <- {f.url}")
    tmp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(f.url) as resp, open(tmp, "wb") as out:
        shutil.copyfileobj(resp, out, length=1 << 20)

    size = tmp.stat().st_size
    if size != f.size:
        tmp.unlink()
        sys.exit(f"error: {dest.name} downloaded {size} bytes, expected {f.size}")
    tmp.rename(dest)
    print(f"done   {dest.name} ({size:,} bytes)")


def main() -> None:
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    for f in EXTERNAL_FILES:
        fetch(f)


if __name__ == "__main__":
    main()
