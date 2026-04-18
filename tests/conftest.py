from pathlib import Path
import shutil
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Isolated copy of schema + vocabularies into a temp dir, plus an empty incidents/."""
    (tmp_path / "incidents").mkdir()
    shutil.copytree(REPO_ROOT / "schema", tmp_path / "schema")
    shutil.copytree(REPO_ROOT / "vocabularies", tmp_path / "vocabularies")
    return tmp_path


@pytest.fixture
def minimal_incident() -> dict:
    return {
        "id": "2020-01-01_example",
        "schema_version": "1.0",
        "event_date": "2020-01-01",
        "event_date_precision": "day",
        "countries_impacted": ["DE"],
        "confirmation_status": "reported",
        "description_en": "A minimal valid example incident.",
        "sources": [
            {"url": "https://example.org/a", "type": "news"}
        ],
        "last_updated": "2026-04-19",
    }
