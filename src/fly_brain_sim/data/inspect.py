"""Profile raw data files: columns, types, row counts, missing values, example values.

Types are whatever DuckDB's sniffer infers from the whole file (sample_size=-1),
so the report reflects the files as they actually are.
"""

import gzip
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import numpy as np

# Files larger than this are profiled by streaming instead of being loaded into
# memory, and their representative values come from a random sample.
LARGE_FILE_BYTES = 1_000_000_000
SAMPLE_ROWS = 1_000_000

FLOAT_TYPES = {"FLOAT", "DOUBLE", "REAL"}


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    null_pct: float
    distinct: int  # exact, except for large files where it is DuckDB's estimate
    min: str | None
    max: str | None
    top_values: list[tuple[str, int]]


@dataclass
class FileProfile:
    path: Path
    size_bytes: int
    rows: int
    columns: list[ColumnProfile] = field(default_factory=list)
    sampled: bool = False
    raw_header: list[str] | None = None


def scan_sql(path: Path, sample_all: bool = True) -> str:
    """SQL table expression that reads `path` with DuckDB."""
    name = path.name.lower()
    p = str(path).replace("'", "''")
    if name.endswith(".parquet"):
        return f"read_parquet('{p}')"
    sample = ", sample_size=-1" if sample_all else ""
    if name.endswith((".tsv", ".tsv.gz")):
        return f"read_csv('{p}', delim='\\t', header=true{sample})"
    if name.endswith((".csv", ".csv.gz")):
        return f"read_csv('{p}', header=true{sample})"
    raise ValueError(f"don't know how to read {path}")


def raw_csv_header(path: Path) -> list[str] | None:
    """Header fields exactly as written in the file (DuckDB renames blank ones)."""
    name = path.name.lower()
    if name.endswith(".parquet"):
        return None
    opener = gzip.open if name.endswith(".gz") else open
    with opener(path, "rt") as f:
        line = f.readline().rstrip("\r\n")
    return line.split("\t" if ".tsv" in name else ",")


def _fmt(v) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if len(s) <= 60 else s[:57] + "..."


def profile_file(path: Path, con: duckdb.DuckDBPyConnection | None = None) -> FileProfile:
    con = con or duckdb.connect()
    size = path.stat().st_size
    large = size > LARGE_FILE_BYTES

    if large:
        source = scan_sql(path, sample_all=False)
        con.execute(
            f"create or replace temp table sample as select * from {source} "
            f"using sample reservoir({SAMPLE_ROWS} rows) repeatable (42)"
        )
        values_from = "sample"
    else:
        con.execute(f"create or replace temp table t as select * from {scan_sql(path)}")
        source = values_from = "t"

    cur = con.execute(f"summarize select * from {source}")
    cols = [d[0] for d in cur.description]
    summary = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    rows = int(summary[0]["count"]) if summary else 0

    if large:  # a second full pass for exact counts isn't worth it
        distinct = {s["column_name"]: int(s["approx_unique"] or 0) for s in summary}
    else:
        names = [s["column_name"] for s in summary]
        counts = con.execute(
            "select " + ", ".join(f"count(distinct {_ident(n)})" for n in names) + " from t"
        ).fetchone()
        distinct = dict(zip(names, counts, strict=True))

    profile = FileProfile(
        path=path, size_bytes=size, rows=rows, sampled=large, raw_header=raw_csv_header(path)
    )
    for s in summary:
        col = s["column_name"]
        q = _ident(col)
        top = con.execute(
            f"select {q}::varchar, count(*) from {values_from} where {q} is not null "
            f"group by 1 order by 2 desc, 1 limit 8"
        ).fetchall()
        profile.columns.append(
            ColumnProfile(
                name=col,
                dtype=s["column_type"],
                null_pct=float(s["null_percentage"] or 0),
                distinct=distinct[col],
                min=_fmt(s["min"]),
                max=_fmt(s["max"]),
                top_values=[(_fmt(v), n) for v, n in top],
            )
        )
    return profile


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def id_columns_read_as_float(profile: FileProfile) -> list[str]:
    """ID-like columns whose inferred type is floating point (i.e. precision is at risk)."""
    return [
        c.name
        for c in profile.columns
        if "id" in c.name.lower().replace("_", " ").split() and c.dtype in FLOAT_TYPES
    ]


def _cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def _values(c: ColumnProfile) -> str:
    if not c.top_values:
        return "(all missing)"
    if c.top_values[0][1] == 1:  # every value unique-ish: counts carry no information
        return "e.g. " + ", ".join(f"`{_cell(v)}`" for v, _ in c.top_values[:3])
    n = min(len(c.top_values), 5)
    return ", ".join(f"`{_cell(v)}` ({cnt:,})" for v, cnt in c.top_values[:n])


@dataclass
class SkeletonZipProfile:
    path: Path
    size_bytes: int
    n_files: int
    uncompressed_bytes: int
    names_ok: bool  # every entry is <18-digit root id>.swc
    header: list[str]  # comment lines of the first file
    sample_size: int
    nodes: tuple[int, int, int]  # min, median, max nodes per file (sample)
    roots_per_file: dict[int, int]  # number of roots -> files (sample)
    labels: dict[int, int]  # SWC label -> nodes (sample)
    with_soma: int  # sampled files with a label-1 node
    radius_nm: tuple[float, float]


def profile_skeleton_zip(path: Path, sample: int = 2000, seed: int = 0) -> SkeletonZipProfile:
    """Summarise the skeleton zip from its listing plus a random sample of SWC files."""
    import random
    import re
    import zipfile

    from fly_brain_sim.data.skeletons import parse_swc

    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        header = [line for line in z.read(names[0]).decode().splitlines() if line.startswith("#")]
        picked = random.Random(seed).sample(names, min(sample, len(names)))
        nodes, roots, labels, soma, rmin, rmax = [], {}, {}, 0, np.inf, -np.inf
        for name in picked:
            sk = parse_swc(z.read(name), int(name[:-4]))
            nodes.append(len(sk))
            r = int((sk.parent < 0).sum())
            roots[r] = roots.get(r, 0) + 1
            for lab, cnt in zip(*np.unique(sk.label, return_counts=True), strict=True):
                labels[int(lab)] = labels.get(int(lab), 0) + int(cnt)
            soma += bool((sk.label == 1).any())
            rmin, rmax = min(rmin, float(sk.radius.min())), max(rmax, float(sk.radius.max()))
    nodes.sort()
    return SkeletonZipProfile(
        path=path,
        size_bytes=path.stat().st_size,
        n_files=len(names),
        uncompressed_bytes=sum(i.file_size for i in infos),
        names_ok=all(re.fullmatch(r"\d{18}\.swc", n) for n in names),
        header=header,
        sample_size=len(picked),
        nodes=(nodes[0], nodes[len(nodes) // 2], nodes[-1]),
        roots_per_file=dict(sorted(roots.items())),
        labels=dict(sorted(labels.items())),
        with_soma=soma,
        radius_nm=(rmin, rmax),
    )


def _render_skeletons(z: SkeletonZipProfile, rel: str, notes: dict[str, str]) -> list[str]:
    out = ["", f"## `{rel}`", ""]
    if rel in notes:
        out += [notes[rel], ""]
    out += [
        f"{z.size_bytes / 1e6:,.1f} MB zip, {z.n_files:,} files, "
        f"{z.uncompressed_bytes / 1e9:,.1f} GB uncompressed. "
        + (
            "Every entry is named `<root_id>.swc` (18-digit root ID)."
            if z.names_ok
            else "**Warning:** some entries are not named `<root_id>.swc`."
        ),
        "",
        "Header of the first file:",
        "",
        "```",
        *z.header,
        "```",
        "",
        f"From a random sample of {z.sample_size:,} files:",
        "",
        f"- nodes per neuron: min {z.nodes[0]:,}, median {z.nodes[1]:,}, max {z.nodes[2]:,}",
        "- roots per file: "
        + ", ".join(f"{k} root(s) in {v:,} files" for k, v in z.roots_per_file.items()),
        "- nodes by SWC label: " + ", ".join(f"{k}: {v:,}" for k, v in z.labels.items()),
        f"- files with a soma node (label 1): {z.with_soma:,}",
        f"- radius: {z.radius_nm[0]:,.0f} to {z.radius_nm[1]:,.0f} nm",
    ]
    return out


def render_markdown(
    profiles: list[FileProfile],
    raw_dir: Path,
    notes: dict[str, str],
    skeletons: list[SkeletonZipProfile] = (),
) -> str:
    out = [
        "# Data dictionary",
        "",
        "Auto-generated by `scripts/inspect_raw.py` from the files in `data/raw/`. "
        "Do not edit by hand; re-run the script instead.",
        "",
        "Types are those inferred by DuckDB from the full file. "
        "*Missing* is the share of NULL / empty cells. "
        "*Distinct* is the exact number of distinct non-missing values "
        "(DuckDB's estimate for the one file marked as large). "
        "*Representative values* are the most frequent values with their counts, "
        "or a few examples when values are (nearly) all unique.",
        "",
        "## Files",
        "",
        "| file | size | rows | columns |",
        "|---|---:|---:|---:|",
    ]
    for p in profiles:
        rel = p.path.relative_to(raw_dir).as_posix()
        out.append(
            f"| [`{rel}`](#{_anchor(rel)}) | {p.size_bytes / 1e6:,.1f} MB | {p.rows:,} "
            f"| {len(p.columns)} |"
        )
    for z in skeletons:
        rel = z.path.relative_to(raw_dir).as_posix()
        out.append(
            f"| [`{rel}`](#{_anchor(rel)}) | {z.size_bytes / 1e6:,.1f} MB "
            f"| {z.n_files:,} files | SWC |"
        )

    for p in profiles:
        rel = p.path.relative_to(raw_dir).as_posix()
        out += ["", f"## `{rel}`", ""]
        if rel in notes:
            out += [notes[rel], ""]
        out.append(f"{p.size_bytes / 1e6:,.1f} MB, {p.rows:,} rows, {len(p.columns)} columns.")
        if p.sampled:
            out.append(
                "Large file: row count, types, missing rates and min/max cover the whole file; "
                "*distinct* is an estimate and representative values come from a random "
                f"sample of {SAMPLE_ROWS:,} rows."
            )
        if p.raw_header is not None:
            blanks = [c.name for c, h in zip(p.columns, p.raw_header, strict=False) if h == ""]
            if blanks:
                out.append(
                    f"The header has blank column name(s); DuckDB names them {', '.join(blanks)}."
                )
        bad = id_columns_read_as_float(p)
        if bad:
            out.append(f"**Warning:** ID columns inferred as floating point: {', '.join(bad)}.")
        out += [
            "",
            "| column | type | missing | distinct | min | max | representative values |",
            "|---|---|---:|---:|---|---|---|",
        ]
        for c in p.columns:
            out.append(
                f"| `{_cell(c.name)}` | {c.dtype} | {c.null_pct:.2f}% | {c.distinct:,} "
                f"| {_cell(c.min or '')} | {_cell(c.max or '')} | {_values(c)} |"
            )
    for z in skeletons:
        out += _render_skeletons(z, z.path.relative_to(raw_dir).as_posix(), notes)
    return "\n".join(out) + "\n"


def _anchor(rel: str) -> str:
    return "".join(ch for ch in rel.lower() if ch.isalnum() or ch in "-_ ").replace(" ", "-")
