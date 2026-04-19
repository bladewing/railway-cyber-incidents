"""Pass 4 — write a neutral English description (and preserve DE when source is German)."""

from __future__ import annotations

from dataclasses import dataclass

from scripts.discover.candidate import Candidate
from scripts.discover.llm import call_haiku_json

PROMPT_TEMPLATE = """\
Write a neutral factual summary of the incident below.

Return JSON ONLY:
{{"description_en": "<1-3 sentences English, <=80 words>", "description_de": <null or <=80 words German original>}}

Rules:
- English text must be neutral, no speculation, no adjectives like "devastating" or "massive".
- If the source language is "{lang}" and "{lang}" == "de", set description_de to a faithful German rendering of the same facts. Otherwise set description_de to null.
- Only facts supported by the text. No invention.

Title: {title}
Source language: {lang}
Text:
{body}
"""


@dataclass(frozen=True)
class SummaryResult:
    description_en: str
    description_de: str | None


def summarize(c: Candidate) -> tuple[SummaryResult, dict]:
    body = c.excerpt or c.title
    prompt = PROMPT_TEMPLATE.format(title=c.title, lang=c.lang, body=body[:6000])
    parsed, meta = call_haiku_json(prompt)
    return (
        SummaryResult(
            description_en=str(parsed.get("description_en") or "").strip(),
            description_de=(parsed.get("description_de") or None),
        ),
        meta,
    )
