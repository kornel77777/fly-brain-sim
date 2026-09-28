"""Filesystem locations used by the data pipeline."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CODEX_DIR = RAW_DIR / "codex"
EXTERNAL_DIR = RAW_DIR / "external"
PROCESSED_DIR = DATA_DIR / "processed"
DB_PATH = PROCESSED_DIR / "flywire_783.duckdb"
DOCS_DIR = REPO_ROOT / "docs"
