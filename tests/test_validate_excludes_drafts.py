import subprocess
import shutil
from pathlib import Path


def test_validate_ignores_drafts_dir(tmp_path, monkeypatch):
    """Put a deliberately broken YAML under incidents/drafts/; validate must still pass."""
    repo = Path(__file__).resolve().parents[1]
    drafts = repo / "incidents" / "drafts"
    drafts.mkdir(exist_ok=True)
    bad = drafts / "0000-00-00_intentionally-broken.yaml"
    bad.write_text("this: is: not: valid: yaml: because: of: too: many: colons\n", encoding="utf-8")
    try:
        proc = subprocess.run(
            ["uv", "run", "python", "scripts/validate.py"],
            cwd=repo, capture_output=True, text=True, check=False,
        )
        assert proc.returncode == 0, f"validate failed: {proc.stdout}\n{proc.stderr}"
    finally:
        bad.unlink(missing_ok=True)
        if not any(drafts.iterdir()):
            drafts.rmdir()
