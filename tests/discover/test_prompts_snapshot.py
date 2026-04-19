from pathlib import Path

from scripts.discover.classify import PROMPT_TEMPLATE as CLASSIFY
from scripts.discover.dedup import DEDUP_PROMPT as DEDUP
from scripts.discover.extract import PROMPT_TEMPLATE as EXTRACT
from scripts.discover.summarize import PROMPT_TEMPLATE as SUMMARIZE

SNAPS = Path(__file__).parent / "fixtures" / "prompts"


def _render_classify():
    return CLASSIFY.format(title="<TITLE>", excerpt="<EXCERPT>")


def _render_dedup():
    return DEDUP.format(title="<TITLE>", date="<DATE>", url="<URL>",
                        excerpt="<EXCERPT>", existing="<EXISTING>")


def _render_extract():
    return EXTRACT.format(body="<BODY>")


def _render_summarize():
    return SUMMARIZE.format(title="<TITLE>", lang="<LANG>", body="<BODY>")


def test_classify_prompt_matches_snapshot():
    assert _render_classify() == (SNAPS / "classify.txt").read_text(encoding="utf-8")


def test_dedup_prompt_matches_snapshot():
    assert _render_dedup() == (SNAPS / "dedup.txt").read_text(encoding="utf-8")


def test_extract_prompt_matches_snapshot():
    assert _render_extract() == (SNAPS / "extract.txt").read_text(encoding="utf-8")


def test_summarize_prompt_matches_snapshot():
    assert _render_summarize() == (SNAPS / "summarize.txt").read_text(encoding="utf-8")
