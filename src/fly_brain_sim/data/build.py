"""Build data/processed/flywire_783.duckdb from the raw files.

Root IDs are 18-digit integers (~7.2e17). A float64 only has 53 bits of
mantissa, so reading them as floats silently turns them into *different* IDs.
Every ID column is therefore given an explicit BIGINT type when read; nothing
ID-related is left to type inference.

Column names are normalised across sources:
    root_id / pre_root_id / post_root_id   neuron IDs
    syn_count                              synapses in a connection
    cell_type                              cell type label
    x_nm, y_nm, z_nm                       positions in nanometres
"""

import os
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import polars as pl

from fly_brain_sim.data.codex import (
    CODEX_HEADERS,
    CONNECTIONS,
    CONNECTIONS_HEADER,
    CONNECTIONS_NO_THRESHOLD,
    read_header,
)
from fly_brain_sim.data.external import NEURON_ANNOTATIONS, SHIU_COMPLETENESS, SHIU_CONNECTIVITY
from fly_brain_sim.data.paths import CODEX_DIR, DB_PATH, EXTERNAL_DIR, RAW_DIR

ID = "BIGINT"


def codex(name: str) -> Path:
    return CODEX_DIR / name


ANNOTATIONS_TSV = EXTERNAL_DIR / NEURON_ANNOTATIONS.filename
COMPLETENESS_CSV = EXTERNAL_DIR / SHIU_COMPLETENESS.filename
CONNECTIVITY_PARQUET = EXTERNAL_DIR / SHIU_CONNECTIVITY.filename

REQUIRED = [
    codex("neurons.csv.gz"),
    codex("classification.csv.gz"),
    codex("names.csv.gz"),
    codex("consolidated_cell_types.csv.gz"),
    codex("cell_stats.csv.gz"),
    codex(CONNECTIONS),
    codex(CONNECTIONS_NO_THRESHOLD),
    codex("coordinates.csv.gz"),
    codex("labels.csv.gz"),
    codex("processed_labels.csv.gz"),
    codex("visual_neuron_types.csv.gz"),
    codex("column_assignment.csv.gz"),
    codex("connectivity_tags.csv.gz"),
    ANNOTATIONS_TSV,
    COMPLETENESS_CSV,
    CONNECTIVITY_PARQUET,
]


def csv(path: Path, ids: list[str], delim: str = ",") -> str:
    """read_csv() call with the given ID columns forced to BIGINT."""
    types = ", ".join(f"'{c}': '{ID}'" for c in ids)
    return f"read_csv('{path}', header=true, delim='{delim}', sample_size=-1, types={{{types}}})"


def xyz_nm(col: str) -> str:
    """Split a '[x y z]' string (nm) into x_nm, y_nm, z_nm."""
    xs = f"(regexp_extract_all({col}, '-?\\d+')::BIGINT[])"
    return f"{xs}[1] as x_nm, {xs}[2] as y_nm, {xs}[3] as z_nm"


@dataclass
class Table:
    name: str
    sources: list[Path]
    sql: str
    description: str


def tables() -> list[Table]:
    neurons = csv(codex("neurons.csv.gz"), ["root_id"])
    classification = csv(codex("classification.csv.gz"), ["root_id"])
    names = csv(codex("names.csv.gz"), ["root_id"])
    cell_types = csv(codex("consolidated_cell_types.csv.gz"), ["root_id"])
    stats = csv(codex("cell_stats.csv.gz"), ["root_id"])
    conn_ids = ["pre_root_id", "post_root_id"]

    return [
        Table(
            "neurons",
            [
                codex("neurons.csv.gz"),
                codex("classification.csv.gz"),
                codex("names.csv.gz"),
                codex("consolidated_cell_types.csv.gz"),
                codex("cell_stats.csv.gz"),
            ],
            f"""
            select
                n.root_id,
                nm.name,
                n."group" as neuropil_group,
                c.flow, c.super_class, c.class, c.sub_class,
                c.hemilineage as ito_lee_hemilineage,
                c.side, c.nerve,
                t.primary_type as cell_type,
                t."additional_type(s)" as additional_cell_types,
                n.nt_type, n.nt_type_score,
                n.ach_avg, n.gaba_avg, n.glut_avg, n.da_avg, n.ser_avg, n.oct_avg,
                s.length_nm, s.area_nm, s.size_nm
            from {neurons} n
            left join {classification} c using (root_id)
            left join {names} nm using (root_id)
            left join {cell_types} t using (root_id)
            left join {stats} s using (root_id)
            order by n.root_id
            """,
            "One row per proofread neuron (Codex neurons + classification + names "
            "+ consolidated cell types + cell stats).",
        ),
        Table(
            "annotations",
            [ANNOTATIONS_TSV],
            f"""
            select * from {csv(ANNOTATIONS_TSV, ["root_id", "supervoxel_id", "nucleus_id"], "\\t")}
            order by root_id
            """,
            "Schlegel et al. 2024 neuron annotations. pos_* and soma_* are in "
            "4x4x40 nm voxels, as in the source.",
        ),
        Table(
            "connections",
            [codex(CONNECTIONS)],
            f"select * from {csv(codex(CONNECTIONS), conn_ids)} order by all",
            "Codex connections, one row per (pre, post, neuropil); neuron pairs with "
            ">= 5 synapses in total.",
        ),
        Table(
            "connections_no_threshold",
            [codex(CONNECTIONS_NO_THRESHOLD)],
            f"select * from {csv(codex(CONNECTIONS_NO_THRESHOLD), conn_ids)} order by all",
            "Codex connections without a synapse threshold.",
        ),
        Table(
            "neuron_neuropils",
            [codex(CONNECTIONS_NO_THRESHOLD)],
            """
            select root_id, neuropil,
                   sum(input_synapses)::BIGINT as input_synapses,
                   sum(output_synapses)::BIGINT as output_synapses
            from (
                select post_root_id as root_id, neuropil,
                       syn_count as input_synapses, 0 as output_synapses
                from connections_no_threshold
                union all
                select pre_root_id, neuropil, 0, syn_count from connections_no_threshold
            )
            group by all
            order by root_id, neuropil
            """,
            "Synapses per neuron per neuropil (derived from connections_no_threshold).",
        ),
        Table(
            "neuron_home_neuropil",
            [codex(CONNECTIONS_NO_THRESHOLD)],
            """
            select root_id, neuropil as home_neuropil, share as home_share
            from (
                select root_id, neuropil,
                       (input_synapses + output_synapses)
                           / sum(input_synapses + output_synapses) over (partition by root_id)
                           as share,
                       row_number() over (
                           partition by root_id
                           order by input_synapses + output_synapses desc, neuropil
                       ) as rank
                from neuron_neuropils
                where neuropil <> 'UNASGD'
            )
            where rank = 1
            order by root_id
            """,
            "The neuropil holding most of each neuron's synapses (inputs + outputs), and its "
            "share of them. Neurons without synapses in any neuropil are absent.",
        ),
        Table(
            "shiu_neurons",
            [COMPLETENESS_CSV],
            "select * from shiu_completeness order by shiu_index",
            "Neurons of the Shiu et al. 2024 model; shiu_index is the 0-based row "
            "position in Completeness_783.csv.",
        ),
        Table(
            "shiu_connections",
            [CONNECTIVITY_PARQUET],
            f"""
            select
                "Presynaptic_ID"::{ID} as pre_root_id,
                "Postsynaptic_ID"::{ID} as post_root_id,
                "Presynaptic_Index" as pre_shiu_index,
                "Postsynaptic_Index" as post_shiu_index,
                "Connectivity" as syn_count,
                "Excitatory" as sign,
                "Excitatory x Connectivity" as signed_syn_count
            from read_parquet('{CONNECTIVITY_PARQUET}')
            order by pre_root_id, post_root_id
            """,
            "Shiu et al. 2024 model connectivity (sign: +1 excitatory, -1 inhibitory).",
        ),
        Table(
            "coordinates",
            [codex("coordinates.csv.gz")],
            f"""
            select root_id, supervoxel_id, {xyz_nm("position")}
            from {csv(codex("coordinates.csv.gz"), ["root_id", "supervoxel_id"])}
            order by all
            """,
            "Codex representative points per neuron, in nm.",
        ),
        Table(
            "labels",
            [codex("labels.csv.gz")],
            f"""
            select root_id, label_id, label, user_id, user_name, user_affiliation,
                   date_created, supervoxel_id, {xyz_nm("position")}
            from {csv(codex("labels.csv.gz"), ["root_id", "supervoxel_id"])}
            order by root_id, label_id
            """,
            "Codex community labels, one row per label.",
        ),
        Table(
            "processed_labels",
            [codex("processed_labels.csv.gz")],
            f"select * from {csv(codex('processed_labels.csv.gz'), ['root_id'])} order by root_id",
            "Codex processed label lists (kept as the source string).",
        ),
        Table(
            "visual_neuron_types",
            [codex("visual_neuron_types.csv.gz")],
            f"""
            select root_id, type as cell_type, family, subsystem, category, side
            from {csv(codex("visual_neuron_types.csv.gz"), ["root_id"])}
            order by root_id
            """,
            "Codex visual system cell types.",
        ),
        Table(
            "column_assignment",
            [codex("column_assignment.csv.gz")],
            f"""
            select root_id, hemisphere, type as cell_type, column_id, x, y, p, q
            from {csv(codex("column_assignment.csv.gz"), ["root_id"])}
            order by root_id
            """,
            "Codex optic lobe column assignments.",
        ),
        Table(
            "connectivity_tags",
            [codex("connectivity_tags.csv.gz")],
            f"""
            select root_id, string_split(connectivity_tag, ',') as connectivity_tags
            from {csv(codex("connectivity_tags.csv.gz"), ["root_id"])}
            order by root_id
            """,
            "Codex network motif tags per neuron, as a list.",
        ),
    ]


def read_completeness() -> pl.DataFrame:
    """Completeness_783.csv with its row order kept as shiu_index.

    Read with polars rather than DuckDB so row order is guaranteed. The first
    column has a blank header; it holds the root ID.
    """
    df = pl.read_csv(
        COMPLETENESS_CSV,
        has_header=True,
        new_columns=["root_id", "completed"],
        schema_overrides={"root_id": pl.Int64, "completed": pl.Boolean},
    )
    return df.with_row_index("shiu_index").select(
        "root_id", pl.col("shiu_index").cast(pl.Int64), "completed"
    )


def check_inputs() -> None:
    missing = [p for p in REQUIRED if not p.exists()]
    if missing:
        lines = "\n  ".join(str(p.relative_to(RAW_DIR)) for p in missing)
        raise SystemExit(
            f"missing raw files under {RAW_DIR}:\n  {lines}\n"
            "Run scripts/fetch_external.py and scripts/import_codex.py first (see README)."
        )
    for name, header in {**CODEX_HEADERS, CONNECTIONS: CONNECTIONS_HEADER}.items():
        p = codex(name)
        if p.exists() and read_header(p) != header:
            raise SystemExit(f"{p} does not have the expected Codex header")


def build(db_path: Path = DB_PATH, log=print) -> None:
    check_inputs()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_name(db_path.name + ".tmp")
    tmp.unlink(missing_ok=True)

    con = duckdb.connect(tmp)
    con.execute("set enable_progress_bar = false")
    completeness = read_completeness()
    con.register("shiu_completeness", completeness)

    info = []
    for t in tables():
        t0 = time.perf_counter()
        con.execute(f"create table {t.name} as {t.sql}")
        con.execute(f"comment on table {t.name} is '{t.description.replace("'", "''")}'")
        rows = con.execute(f"select count(*) from {t.name}").fetchone()[0]
        log(f"  {t.name:<26} {rows:>12,} rows  ({time.perf_counter() - t0:.1f}s)")
        for src in t.sources:
            info.append((t.name, src.relative_to(RAW_DIR).as_posix(), src.stat().st_size, rows))

    con.execute(
        "create table build_info (table_name varchar, source varchar, source_bytes bigint, "
        "rows bigint)"
    )
    con.executemany("insert into build_info values (?, ?, ?, ?)", info)
    con.execute("checkpoint")
    con.close()
    os.replace(tmp, db_path)
