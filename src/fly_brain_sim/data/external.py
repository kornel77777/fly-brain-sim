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
ANNOTATIONS_COMMIT = "8587524c1748ce5ef2080822a2fc890fc03bf597"

SHIU_CONNECTIVITY = ExternalFile(SHIU_REPO, SHIU_COMMIT, "Connectivity_783.parquet", 100_804_642)
SHIU_COMPLETENESS = ExternalFile(SHIU_REPO, SHIU_COMMIT, "Completeness_783.csv", 3_327_347)
NEURON_ANNOTATIONS = ExternalFile(
    ANNOTATIONS_REPO,
    ANNOTATIONS_COMMIT,
    "supplemental_files/Supplemental_file1_neuron_annotations.tsv",
    31_718_505,
)

EXTERNAL_FILES = (SHIU_CONNECTIVITY, SHIU_COMPLETENESS, NEURON_ANNOTATIONS)
