import csv
import subprocess
from pathlib import Path


def test_build_release_ignores_drafts_dir(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    drafts = repo / "incidents" / "drafts"
    drafts.mkdir(exist_ok=True)
    stub = drafts / "9999-12-31_draft-only.yaml"
    stub.write_text(
        "id: 9999-12-31_draft-only\nschema_version: \"1.0\"\n"
        "event_date: 9999-12-31\nevent_date_precision: day\n"
        "countries_impacted: [DE]\nconfirmation_status: reported\n"
        "description_en: Draft only.\nsources:\n  - url: https://e.com/\n    type: news\n"
        "last_updated: 2026-04-19\n",
        encoding="utf-8",
    )
    try:
        subprocess.run(
            ["uv", "run", "python", "scripts/build_release.py"],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        csv_path = repo / "dist" / "incidents.csv"
        ids = {row["id"] for row in csv.DictReader(csv_path.open())}
        assert "9999-12-31_draft-only" not in ids
    finally:
        stub.unlink(missing_ok=True)
        if not any(drafts.iterdir()):
            drafts.rmdir()
