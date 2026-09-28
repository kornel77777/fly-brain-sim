"""Files downloaded by hand from FlyWire Codex (https://codex.flywire.ai/api/download).

The browser saves them under display names such as "Neurons Data.csv.gz", so
each file is identified by its CSV header instead and stored in
data/raw/codex/ under the canonical name below.
"""

import gzip
import re
import zipfile
from pathlib import Path

import duckdb

# canonical filename -> exact header line of the file
CODEX_HEADERS = {
    "neurons.csv.gz": "root_id,group,nt_type,nt_type_score,da_avg,ser_avg,gaba_avg,glut_avg,"
    "ach_avg,oct_avg",
    "classification.csv.gz": "root_id,flow,super_class,class,sub_class,hemilineage,side,nerve",
    "cell_stats.csv.gz": "root_id,length_nm,area_nm,size_nm",
    "column_assignment.csv.gz": "root_id,hemisphere,type,column_id,x,y,p,q",
    "connectivity_tags.csv.gz": "root_id,connectivity_tag",
    "consolidated_cell_types.csv.gz": "root_id,primary_type,additional_type(s)",
    "coordinates.csv.gz": "root_id,position,supervoxel_id",
    "labels.csv.gz": "root_id,label,user_id,position,supervoxel_id,label_id,date_created,"
    "user_name,user_affiliation",
    "names.csv.gz": "root_id,name,group",
    "processed_labels.csv.gz": "root_id,processed_labels",
    "visual_neuron_types.csv.gz": "root_id,type,family,subsystem,category,side",
    "fafb_v783_princeton_synapse_table.csv.gz": "pre_x,pre_y,pre_z,ctr_x,ctr_y,ctr_z,post_x,"
    "post_y,post_z,size,pre_root_id_720575940,post_root_id_720575940,neuropil",
}

# Both connection downloads share this header; they are told apart by content.
CONNECTIONS_HEADER = "pre_root_id,post_root_id,neuropil,syn_count,nt_type"
CONNECTIONS = "connections.csv.gz"  # pairs with >= 5 synapses in total
CONNECTIONS_NO_THRESHOLD = "connections_no_threshold.csv.gz"
CONNECTION_THRESHOLD = 5

SYNAPSE_TABLE = "fafb_v783_princeton_synapse_table.csv.gz"

# Skeletons ("LOD1 Healed" on Codex): a zip of <root_id>.swc files, in nm.
SKELETONS = "sk_lod1_783_healed.zip"
SWC_NAME = re.compile(r"\d{18}\.swc")

# Files this big are symlinked into data/raw/codex/ instead of copied.
LINK_ABOVE_BYTES = 1_000_000_000


def read_header(path: Path) -> str:
    with gzip.open(path, "rt") as f:
        return f.readline().strip()


def min_pair_synapses(path: Path) -> int:
    """Smallest total synapse count of any (pre, post) pair across all neuropils."""
    sql = f"""
        select min(s) from (
            select sum(syn_count) as s
            from read_csv('{path}', types={{'pre_root_id': 'BIGINT', 'post_root_id': 'BIGINT'}})
            group by pre_root_id, post_root_id
        )
    """
    return duckdb.sql(sql).fetchone()[0]


def is_skeleton_zip(path: Path) -> bool:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    return bool(names) and all(SWC_NAME.fullmatch(n) for n in names)


def classify(path: Path) -> str | None:
    """Return the canonical filename for a Codex download, or None if unknown."""
    if path.suffix == ".zip":
        return SKELETONS if is_skeleton_zip(path) else None
    header = read_header(path)
    if header == CONNECTIONS_HEADER:
        if min_pair_synapses(path) >= CONNECTION_THRESHOLD:
            return CONNECTIONS
        return CONNECTIONS_NO_THRESHOLD
    for name, expected in CODEX_HEADERS.items():
        if header == expected:
            return name
    return None
