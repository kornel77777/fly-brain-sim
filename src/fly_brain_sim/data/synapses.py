"""Build data/processed/synapses_783.duckdb from the Codex synapse table.

Kept separate from the main database because it is ~80M rows and only the
viewer needs it. The source stores root IDs without their shared 720575940
prefix; they are rebuilt arithmetically (prefix * 10**9 + suffix), which is
exact for BIGINT and also correct if a suffix had leading zeros.

Rows are sorted by (pre_root_id, post_root_id) so DuckDB's zone maps make
lookups by presynaptic neuron cheap; lookups by postsynaptic neuron scan one
BIGINT column, which is still fast.
"""

import os
from pathlib import Path

import duckdb

from fly_brain_sim.data.codex import SYNAPSE_TABLE
from fly_brain_sim.data.paths import CODEX_DIR, SYNAPSES_DB_PATH

SOURCE = CODEX_DIR / SYNAPSE_TABLE
ID_PREFIX = 720575940 * 10**9


def build(db_path: Path = SYNAPSES_DB_PATH, source: Path = SOURCE) -> int:
    if not source.exists():
        raise SystemExit(f"{source} not found; run scripts/import_codex.py first (see README)")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_name(db_path.name + ".tmp")
    tmp.unlink(missing_ok=True)

    con = duckdb.connect(tmp)
    con.execute("set enable_progress_bar = false")
    ints = {
        c: "INTEGER"
        for c in [
            "pre_x",
            "pre_y",
            "pre_z",
            "ctr_x",
            "ctr_y",
            "ctr_z",
            "post_x",
            "post_y",
            "post_z",
            "size",
        ]
    }
    ids = {"pre_root_id_720575940": "BIGINT", "post_root_id_720575940": "BIGINT"}
    types = ", ".join(f"'{k}': '{v}'" for k, v in {**ints, **ids}.items())
    con.execute(
        f"""
        create table synapses as
        select
            {ID_PREFIX} + pre_root_id_720575940 as pre_root_id,
            {ID_PREFIX} + post_root_id_720575940 as post_root_id,
            neuropil,
            size,
            pre_x, pre_y, pre_z,
            ctr_x, ctr_y, ctr_z,
            post_x, post_y, post_z
        from read_csv('{source}', header=true, types={{{types}}})
        order by pre_root_id, post_root_id
        """
    )
    con.execute(
        "comment on table synapses is 'Princeton synapse table v783; positions in nm "
        "(pre = presynaptic point, ctr = cleft centre, post = postsynaptic point)'"
    )
    rows = con.execute("select count(*) from synapses").fetchone()[0]
    con.execute("checkpoint")
    con.close()
    os.replace(tmp, db_path)
    return rows
