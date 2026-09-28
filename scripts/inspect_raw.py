"""Profile every file under data/raw/ and write docs/data_dictionary.md.

Usage: uv run python scripts/inspect_raw.py
"""

import sys
import time

import duckdb

from fly_brain_sim.data.codex import is_skeleton_zip
from fly_brain_sim.data.inspect import (
    id_columns_read_as_float,
    profile_file,
    profile_skeleton_zip,
    render_markdown,
)
from fly_brain_sim.data.paths import DOCS_DIR, RAW_DIR

CODEX = "Downloaded by hand from FlyWire Codex (https://codex.flywire.ai/api/download), v783."
SHIU = "From philshiu/Drosophila_brain_model (Shiu et al. 2024), used by the LIF brain model."
FAFB = "From flyconnectome/flywire_annotations (Schlegel et al. 2024), Supplemental file 1."

NOTES = {
    "codex/cell_stats.csv.gz": f"{CODEX} Morphology stats per neuron.",
    "codex/classification.csv.gz": f"{CODEX} Hierarchical annotations (flow / super class / "
    "class / sub class) per neuron.",
    "codex/column_assignment.csv.gz": f"{CODEX} Optic lobe column assignments.",
    "codex/connections.csv.gz": f"{CODEX} Thresholded connections: one row per "
    "(pre, post, neuropil), keeping neuron pairs with at least 5 synapses in total.",
    "codex/connections_no_threshold.csv.gz": f"{CODEX} All connections, no synapse threshold.",
    "codex/connectivity_tags.csv.gz": f"{CODEX} Network motif tags per neuron.",
    "codex/consolidated_cell_types.csv.gz": f"{CODEX} Consolidated cell type per neuron.",
    "codex/coordinates.csv.gz": f"{CODEX} Representative point(s) per neuron "
    "(`position` is a bracketed x y z string in nm).",
    "codex/fafb_v783_princeton_synapse_table.csv.gz": f"{CODEX} Individual synapses. "
    "Symlink to the original download. Root IDs are stored without their common "
    "`720575940` prefix (see column names).",
    "codex/sk_lod1_783_healed.zip": f'{CODEX} Neuron skeletons ("LOD1 healed"), one SWC '
    "file per neuron, positions and radii in nm. Symlink to the original download.",
    "codex/labels.csv.gz": f"{CODEX} Community labels (one row per label, with author).",
    "codex/names.csv.gz": f"{CODEX} Unique neuron names.",
    "codex/neurons.csv.gz": f"{CODEX} One row per proofread neuron with neurotransmitter "
    "predictions.",
    "codex/processed_labels.csv.gz": f"{CODEX} Cleaned-up label lists per neuron.",
    "codex/visual_neuron_types.csv.gz": f"{CODEX} Visual system cell types.",
    "external/Completeness_783.csv": f"{SHIU} One row per neuron; its row order defines the "
    "neuron index used in the model. The first column (root ID) has no header.",
    "external/Connectivity_783.parquet": f"{SHIU} Signed synapse counts per neuron pair; "
    "`Presynaptic_Index`/`Postsynaptic_Index` refer to rows of Completeness_783.csv.",
    "external/Supplemental_file1_neuron_annotations.tsv": f"{FAFB} Neuron annotations "
    "(cell types, hemilineages, predicted and known neurotransmitters, ...).",
}

DATA_SUFFIXES = (".csv", ".csv.gz", ".tsv", ".tsv.gz", ".parquet")


def main() -> None:
    files = sorted(
        p for p in RAW_DIR.rglob("*") if p.is_file() and p.name.lower().endswith(DATA_SUFFIXES)
    )
    if not files:
        sys.exit(f"no data files under {RAW_DIR}")

    con = duckdb.connect()
    profiles = []
    for path in files:
        t0 = time.perf_counter()
        print(f"inspect {path.relative_to(RAW_DIR)} ...", end=" ", flush=True)
        p = profile_file(path, con)
        print(f"{p.rows:,} rows, {len(p.columns)} cols ({time.perf_counter() - t0:.0f}s)")
        if bad := id_columns_read_as_float(p):
            print(f"  WARNING: ID columns read as float: {bad}")
        profiles.append(p)

    skeletons = []
    for path in sorted(RAW_DIR.rglob("*.zip")):
        if not is_skeleton_zip(path):
            print(f"skip    {path.relative_to(RAW_DIR)} (not a skeleton zip)")
            continue
        t0 = time.perf_counter()
        print(f"inspect {path.relative_to(RAW_DIR)} ...", end=" ", flush=True)
        z = profile_skeleton_zip(path)
        print(f"{z.n_files:,} files ({time.perf_counter() - t0:.0f}s)")
        skeletons.append(z)

    unknown = [p.path.relative_to(RAW_DIR).as_posix() for p in [*profiles, *skeletons]]
    unknown = [u for u in unknown if u not in NOTES]
    if unknown:
        print(f"note: no description for {unknown}")

    DOCS_DIR.mkdir(exist_ok=True)
    out = DOCS_DIR / "data_dictionary.md"
    out.write_text(render_markdown(profiles, RAW_DIR, NOTES, skeletons))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
