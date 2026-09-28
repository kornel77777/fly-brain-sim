"""External files fetched from GitHub, pinned to specific commits."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalFile:
    repo: str
    commit: str
    path: str
    size: int  # bytes, as reported by the GitHub contents API at `commit`

    @property
    def filename(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def url(self) -> str:
        return f"https://raw.githubusercontent.com/{self.repo}/{self.commit}/{self.path}"


SHIU_REPO = "philshiu/Drosophila_brain_model"
SHIU_COMMIT = "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
ANNOTATIONS_REPO = "flyconnectome/flywire_annotations"
# Last revision of the annotation file before the v3.0 update (Oct 2025). It has
# exactly the 139,255 root IDs of the 783 release; later revisions replace a few
# IDs with ones that are not in 783.
ANNOTATIONS_COMMIT = "c294fba426f5abe861289bdc1171188026646b04"

SHIU_CONNECTIVITY = ExternalFile(SHIU_REPO, SHIU_COMMIT, "Connectivity_783.parquet", 100_804_642)
SHIU_COMPLETENESS = ExternalFile(SHIU_REPO, SHIU_COMMIT, "Completeness_783.csv", 3_327_347)
NEURON_ANNOTATIONS = ExternalFile(
    ANNOTATIONS_REPO,
    ANNOTATIONS_COMMIT,
    "supplemental_files/Supplemental_file1_neuron_annotations.tsv",
    27_015_208,
)

EXTERNAL_FILES = (SHIU_CONNECTIVITY, SHIU_COMPLETENESS, NEURON_ANNOTATIONS)
