# Incident Discovery Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-stage pipeline that discovers new railway cyber incidents from curated aggregators and writes `needs_review: true` stubs to `incidents/drafts/`, using the Claude Code subscription (via the `claude` CLI) for cheap Haiku-only LLM work.

**Architecture:** Stage 1 is deterministic Python (httpx + BeautifulSoup + pypdf) that produces `dist/candidates.json`. Stage 2 runs four Haiku passes per candidate (classify → dedup → extract → summarise) via `subprocess.run(["claude", "-p", ...])` and writes YAML stubs. Draft stubs compose with the existing v0.2.0 enrichment subagent flow via a thin `scripts/enrich.py` wrapper; `promote_drafts.py` remains the final atomic move.

**Tech Stack:** Python ≥3.11, uv, pytest, ruff, PyYAML, httpx, beautifulsoup4, pypdf, jsonschema. LLM transport: `claude` CLI (subprocess, uses `claude login` session).

**Spec:** `docs/superpowers/specs/2026-04-19-incident-discovery-pipeline-design.md`

---

## Task 1: Add runtime dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Check current dependencies**

Run: `grep -A 30 '\[project\]' pyproject.toml`
Expected: see current `dependencies =` list. Note which of `httpx`, `beautifulsoup4`, `pypdf` are missing.

- [ ] **Step 2: Add missing deps to `[project].dependencies`**

Add any of these that are not already present:

```toml
"httpx>=0.27",
"beautifulsoup4>=4.12",
"pypdf>=4.0",
```

- [ ] **Step 3: Sync and confirm**

Run: `uv sync`
Expected: lockfile updates, no errors.

Run: `uv run python -c "import httpx, bs4, pypdf; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add httpx, beautifulsoup4, pypdf for discovery pipeline"
```

---

## Task 2: Schema bump — add optional provenance fields

**Files:**
- Modify: `schema/incident.schema.json`
- Test: `tests/test_schema_provenance.py` (create)

- [ ] **Step 1: Inspect the current provenance branch**

Run: `grep -n provenance schema/incident.schema.json`
Note the existing `provenance` object shape (should already allow `needs_review`).

- [ ] **Step 2: Write the failing test**

Create `tests/test_schema_provenance.py`:

```python
import json
from pathlib import Path
import jsonschema

SCHEMA = json.loads(Path("schema/incident.schema.json").read_text())


def _minimal_incident(**extra_provenance):
    return {
        "id": "2026-04-19_test",
        "schema_version": "1.0",
        "event_date": "2026-04-19",
        "event_date_precision": "day",
        "countries_impacted": ["DE"],
        "confirmation_status": "reported",
        "description_en": "Test.",
        "sources": [{"url": "https://example.org/x", "type": "news"}],
        "last_updated": "2026-04-19",
        "provenance": {"needs_review": True, **extra_provenance},
    }


def test_provenance_accepts_discovered_by():
    jsonschema.validate(_minimal_incident(discovered_by="discover_incidents"), SCHEMA)


def test_provenance_accepts_aggregator():
    jsonschema.validate(_minimal_incident(aggregator="konbriefing"), SCHEMA)


def test_provenance_accepts_haiku_classify_confidence():
    jsonschema.validate(_minimal_incident(haiku_classify_confidence=0.82), SCHEMA)


def test_provenance_rejects_bad_confidence_type():
    with _pytest_raises():
        jsonschema.validate(_minimal_incident(haiku_classify_confidence="high"), SCHEMA)


def _pytest_raises():
    import pytest
    return pytest.raises(jsonschema.ValidationError)
```

- [ ] **Step 3: Run the test — confirm failure**

Run: `uv run pytest tests/test_schema_provenance.py -v`
Expected: the three accept tests FAIL because the schema rejects unknown properties (or PASS if schema permits additionalProperties — in which case the "bad type" test still needs the schema tightened).

- [ ] **Step 4: Edit the schema**

Under `properties.provenance.properties`, add:

```json
"discovered_by": { "type": "string" },
"aggregator":    { "type": "string" },
"haiku_classify_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
```

Ensure `additionalProperties` stays `false` if it already is, so the negative test works. If the current schema has `additionalProperties: true` under `provenance`, change it to `false`.

- [ ] **Step 5: Run test — confirm pass**

Run: `uv run pytest tests/test_schema_provenance.py -v`
Expected: all four tests PASS.

- [ ] **Step 6: Confirm existing dataset still validates**

Run: `make validate`
Expected: `0` errors.

- [ ] **Step 7: Commit**

```bash
git add schema/incident.schema.json tests/test_schema_provenance.py
git commit -m "feat(schema): add optional provenance.{discovered_by,aggregator,haiku_classify_confidence}"
```

---

## Task 3: Rail keyword vocabulary

**Files:**
- Create: `vocabularies/rail_keywords.yaml`
- Create: `scripts/discover/__init__.py`
- Create: `scripts/discover/keywords.py`
- Test: `tests/discover/__init__.py`, `tests/discover/test_keywords.py`

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p scripts/discover tests/discover
touch scripts/discover/__init__.py tests/discover/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `tests/discover/test_keywords.py`:

```python
from scripts.discover.keywords import load_rail_keywords, matches_rail


def test_load_returns_nonempty_lowercased_set():
    kws = load_rail_keywords()
    assert isinstance(kws, frozenset)
    assert len(kws) >= 10
    assert all(k == k.lower() for k in kws)
    assert "railway" in kws


def test_matches_rail_is_case_insensitive():
    kws = {"railway", "deutsche bahn"}
    assert matches_rail("A RAILWAY was attacked", kws)
    assert matches_rail("Deutsche Bahn AG confirms breach", kws)
    assert not matches_rail("A bakery was attacked", kws)


def test_matches_rail_whole_word_only():
    kws = {"rail"}
    assert matches_rail("rail network down", kws)
    assert not matches_rail("email server down", kws)
```

- [ ] **Step 3: Run — confirm failure**

Run: `uv run pytest tests/discover/test_keywords.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 4: Create the vocabulary file**

`vocabularies/rail_keywords.yaml`:

```yaml
# Rail-adjacency keywords used by discovery adapters to filter broad
# aggregator feeds. Not a controlled enum — purely a filter list.
# Case-insensitive match; adapters do whole-word matching.
keywords:
  - rail
  - railway
  - railroad
  - train
  - metro
  - subway
  - tram
  - transit
  # Operators (add as discovered):
  - "Deutsche Bahn"
  - DB Schenker
  - SNCF
  - Trenitalia
  - ÖBB
  - NS
  - Amtrak
  - ProRail
  - Network Rail
  - Renfe
  - JR East
  - CFL
  - CD Cargo
```

- [ ] **Step 5: Implement the loader**

Create `scripts/discover/keywords.py`:

```python
"""Rail-adjacency keyword loader and whole-word matcher."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

_VOCAB = Path(__file__).resolve().parents[2] / "vocabularies" / "rail_keywords.yaml"


@lru_cache(maxsize=1)
def load_rail_keywords() -> frozenset[str]:
    data = yaml.safe_load(_VOCAB.read_text(encoding="utf-8"))
    return frozenset(k.lower() for k in data["keywords"])


def matches_rail(text: str, keywords: frozenset[str] | set[str] | None = None) -> bool:
    kws = keywords if keywords is not None else load_rail_keywords()
    hay = text.lower()
    for k in kws:
        if re.search(rf"\b{re.escape(k.lower())}\b", hay):
            return True
    return False
```

- [ ] **Step 6: Run — confirm pass**

Run: `uv run pytest tests/discover/test_keywords.py -v`
Expected: all three tests PASS.

- [ ] **Step 7: Commit**

```bash
git add vocabularies/rail_keywords.yaml scripts/discover/ tests/discover/__init__.py tests/discover/test_keywords.py
git commit -m "feat(discover): rail keyword vocabulary and whole-word matcher"
```

---

## Task 4: Candidate dataclass

**Files:**
- Create: `scripts/discover/candidate.py`
- Test: `tests/discover/test_candidate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_candidate.py`:

```python
import json

from scripts.discover.candidate import Candidate


def test_candidate_roundtrip_json():
    c = Candidate(
        url="https://example.org/a",
        title="Rail hit",
        raw_date="2024-03-01",
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt="snippet",
        discovered_at="2026-04-19",
    )
    payload = c.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert Candidate.from_dict(payload) == c


def test_candidate_requires_absolute_url():
    import pytest
    with pytest.raises(ValueError):
        Candidate(
            url="/relative",
            title="t",
            raw_date="2024-01-01",
            source_id="x",
            source_type="news",
            lang="en",
            excerpt="",
            discovered_at="2026-04-19",
        )
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_candidate.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Create `scripts/discover/candidate.py`:

```python
"""Candidate dataclass — the shared shape between Stage 1 and Stage 2."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Candidate:
    url: str
    title: str
    raw_date: str | None
    source_id: str
    source_type: str
    lang: str
    excerpt: str
    discovered_at: str

    def __post_init__(self) -> None:
        if not (self.url.startswith("http://") or self.url.startswith("https://")):
            raise ValueError(f"Candidate.url must be absolute http(s), got {self.url!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        return cls(**d)
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_candidate.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/candidate.py tests/discover/test_candidate.py
git commit -m "feat(discover): Candidate dataclass"
```

---

## Task 5: Aggregators config file and loader

**Files:**
- Create: `aggregators.yaml`
- Create: `scripts/discover/aggregators_config.py`
- Test: `tests/discover/test_aggregators_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_aggregators_config.py`:

```python
from scripts.discover.aggregators_config import load_aggregators


def test_load_returns_at_least_five_enabled_sources():
    aggs = load_aggregators()
    enabled_ids = {a.id for a in aggs if a.enabled}
    assert {"konbriefing", "eurepoc", "enisa_transport", "ransomware_live", "bsi_lagebericht"} <= enabled_ids


def test_each_aggregator_has_kind_and_url_or_pdfs():
    for a in load_aggregators():
        assert a.kind in {"html", "json", "pdf"}
        assert a.id
        assert a.url or a.pdfs  # at least one source input
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_aggregators_config.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Create aggregators.yaml**

At project root, create `aggregators.yaml`:

```yaml
# Curated sources for the discovery pipeline. Editable by
# non-dev contributors. See docs/superpowers/specs/2026-04-19-
# incident-discovery-pipeline-design.md for the list rationale.
aggregators:
  - id: konbriefing
    kind: html
    enabled: true
    url: https://konbriefing.com/en-topics/cyber-attacks-railway.html
    source_type: news

  - id: eurepoc
    kind: json
    enabled: true
    url: https://eurepoc.eu/api/incidents?sector=Transport
    source_type: database

  - id: enisa_transport
    kind: pdf
    enabled: true
    pdfs:
      # Add URLs to annual Transport Threat Landscape PDFs here.
      # Left empty until maintainer supplies stable URLs.
    source_type: advisory

  - id: ransomware_live
    kind: json
    enabled: true
    url: https://api.ransomware.live/v2/recentvictims
    source_type: leak_site

  - id: bsi_lagebericht
    kind: pdf
    enabled: true
    pdfs:
      # BSI annual Lagebericht PDFs; populate on rollout.
    source_type: advisory
```

- [ ] **Step 4: Implement loader**

Create `scripts/discover/aggregators_config.py`:

```python
"""Loader for aggregators.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_CONFIG = Path(__file__).resolve().parents[2] / "aggregators.yaml"


@dataclass(frozen=True)
class AggregatorConfig:
    id: str
    kind: str
    enabled: bool
    source_type: str
    url: str | None = None
    pdfs: tuple[str, ...] = field(default_factory=tuple)


def load_aggregators(path: Path = _CONFIG) -> list[AggregatorConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[AggregatorConfig] = []
    for entry in data["aggregators"]:
        out.append(
            AggregatorConfig(
                id=entry["id"],
                kind=entry["kind"],
                enabled=entry.get("enabled", True),
                source_type=entry["source_type"],
                url=entry.get("url"),
                pdfs=tuple(entry.get("pdfs") or ()),
            )
        )
    return out
```

- [ ] **Step 5: Run — confirm pass**

Run: `uv run pytest tests/discover/test_aggregators_config.py -v`
Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add aggregators.yaml scripts/discover/aggregators_config.py tests/discover/test_aggregators_config.py
git commit -m "feat(discover): aggregators.yaml config and loader"
```

---

## Task 6: LLM subprocess wrapper

**Files:**
- Create: `scripts/discover/llm.py`
- Test: `tests/discover/test_llm.py`

The wrapper shells out to `claude -p --model haiku --output-format json` and parses both the outer JSON (with `result`, `usage`, `total_cost_usd`) and the inner `result` which our prompts always demand be JSON.

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_llm.py`:

```python
import json
import subprocess
from unittest.mock import patch

import pytest

from scripts.discover.llm import LLMError, call_haiku_json


def _fake_run(outer_result, cost=0.001):
    payload = {
        "result": outer_result if isinstance(outer_result, str) else json.dumps(outer_result),
        "total_cost_usd": cost,
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }

    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=json.dumps(payload), stderr=""
        )

    return _run


def test_happy_path_returns_parsed_inner_json_plus_cost():
    with patch("subprocess.run", side_effect=_fake_run({"is_rail_cyber": True, "confidence": 0.9})):
        result, meta = call_haiku_json("prompt")
    assert result == {"is_rail_cyber": True, "confidence": 0.9}
    assert meta["cost_usd"] == 0.001
    assert meta["input_tokens"] == 100


def test_retries_once_on_invalid_inner_json():
    calls = {"n": 0}

    def _run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            outer = {"result": "not json", "total_cost_usd": 0.001,
                     "usage": {"input_tokens": 10, "output_tokens": 2}}
        else:
            outer = {"result": json.dumps({"ok": True}), "total_cost_usd": 0.002,
                     "usage": {"input_tokens": 20, "output_tokens": 5}}
        return subprocess.CompletedProcess(args=cmd, returncode=0,
                                           stdout=json.dumps(outer), stderr="")

    with patch("subprocess.run", side_effect=_run):
        result, meta = call_haiku_json("p", retries=1)
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_raises_after_exhausting_retries():
    def _run(cmd, **kwargs):
        outer = {"result": "never json", "total_cost_usd": 0.0,
                 "usage": {"input_tokens": 0, "output_tokens": 0}}
        return subprocess.CompletedProcess(args=cmd, returncode=0,
                                           stdout=json.dumps(outer), stderr="")

    with patch("subprocess.run", side_effect=_run):
        with pytest.raises(LLMError):
            call_haiku_json("p", retries=1)


def test_passes_model_flag():
    captured = {}

    def _run(cmd, **kwargs):
        captured["cmd"] = cmd
        outer = {"result": "{}", "total_cost_usd": 0.0,
                 "usage": {"input_tokens": 0, "output_tokens": 0}}
        return subprocess.CompletedProcess(args=cmd, returncode=0,
                                           stdout=json.dumps(outer), stderr="")

    with patch("subprocess.run", side_effect=_run):
        call_haiku_json("p")
    assert "--model" in captured["cmd"]
    idx = captured["cmd"].index("--model")
    assert captured["cmd"][idx + 1] == "haiku"
    assert "--output-format" in captured["cmd"]
    assert "json" in captured["cmd"]
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_llm.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `scripts/discover/llm.py`:

```python
"""Thin wrapper around the `claude` CLI for Haiku JSON calls."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


class LLMError(RuntimeError):
    """Raised when the LLM produces unusable output after retries."""


@dataclass
class CallMeta:
    cost_usd: float
    input_tokens: int
    output_tokens: int

    def as_dict(self) -> dict:
        return {
            "cost_usd": self.cost_usd,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


def call_haiku_json(
    prompt: str,
    *,
    retries: int = 1,
    timeout_s: int = 60,
) -> tuple[dict | list, dict]:
    """Call `claude -p --model haiku --output-format json` and return (parsed_inner, meta).

    Adds a strict-JSON reminder on retry. Raises LLMError when no retry
    produces valid JSON.
    """
    last_err: Exception | None = None
    attempt_prompt = prompt
    for attempt in range(retries + 1):
        proc = subprocess.run(
            [
                "claude",
                "-p",
                attempt_prompt,
                "--model",
                "haiku",
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=True,
        )
        outer = json.loads(proc.stdout)
        raw = outer.get("result", "")
        meta = CallMeta(
            cost_usd=float(outer.get("total_cost_usd", 0.0)),
            input_tokens=int(outer.get("usage", {}).get("input_tokens", 0)),
            output_tokens=int(outer.get("usage", {}).get("output_tokens", 0)),
        ).as_dict()
        try:
            parsed = json.loads(raw if isinstance(raw, str) else json.dumps(raw))
            return parsed, meta
        except json.JSONDecodeError as e:
            last_err = e
            attempt_prompt = (
                prompt + "\n\nReturn ONLY valid JSON. No prose. No code fences."
            )
    raise LLMError(f"Haiku returned unparseable JSON after {retries + 1} attempts: {last_err}")
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_llm.py -v`
Expected: all four tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/llm.py tests/discover/test_llm.py
git commit -m "feat(discover): claude CLI subprocess wrapper with retry and cost tracking"
```

---

## Task 7: Konbriefing adapter (HTML)

**Files:**
- Create: `scripts/discover/adapters/__init__.py`
- Create: `scripts/discover/adapters/konbriefing.py`
- Create: `tests/discover/fixtures/konbriefing_sample.html`
- Test: `tests/discover/test_adapter_konbriefing.py`

- [ ] **Step 1: Create package init**

```bash
mkdir -p scripts/discover/adapters tests/discover/fixtures
touch scripts/discover/adapters/__init__.py
```

- [ ] **Step 2: Capture a minimal HTML fixture**

Create `tests/discover/fixtures/konbriefing_sample.html` with a stripped-down copy of the real page structure. Minimum viable shape:

```html
<!doctype html>
<html lang="en">
<body>
<ul class="cyberattack-list">
  <li>
    <span class="date">2024-03-01</span>
    <a href="https://news.example.com/db-schenker-hack">
      DB Schenker confirms ransomware attack
    </a>
    <p>Short summary of the attack on rail freight operations.</p>
  </li>
  <li>
    <span class="date">2023-08-14</span>
    <a href="https://news.example.com/metro-attack">
      Paris metro operator hit by cyberattack
    </a>
    <p>Metro network disruption reported.</p>
  </li>
</ul>
</body>
</html>
```

**Note:** the real konbriefing page may not use `class="cyberattack-list"` or `class="date"`. Before writing the parser, fetch the live page and adjust the fixture selectors to match. Run:

```bash
uv run python -c "import httpx; print(httpx.get('https://konbriefing.com/en-topics/cyber-attacks-railway.html', follow_redirects=True).text[:2000])"
```

Pick selectors that survive minor edits. Document the chosen selectors inline.

- [ ] **Step 3: Write the failing test**

Create `tests/discover/test_adapter_konbriefing.py`:

```python
from pathlib import Path

from scripts.discover.adapters.konbriefing import parse
from scripts.discover.candidate import Candidate

FIXTURE = Path(__file__).parent / "fixtures" / "konbriefing_sample.html"


def test_parse_extracts_candidates_from_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    candidates = parse(html, discovered_at="2026-04-19")
    assert len(candidates) == 2
    c = candidates[0]
    assert isinstance(c, Candidate)
    assert c.url.startswith("https://")
    assert "db schenker" in c.title.lower()
    assert c.raw_date == "2024-03-01"
    assert c.source_id == "konbriefing"
    assert c.source_type == "news"
    assert c.lang == "en"
    assert c.discovered_at == "2026-04-19"
```

- [ ] **Step 4: Run — confirm failure**

Run: `uv run pytest tests/discover/test_adapter_konbriefing.py -v`
Expected: ImportError.

- [ ] **Step 5: Implement**

Create `scripts/discover/adapters/konbriefing.py`:

```python
"""Konbriefing adapter — parses the 'Cyber Attacks on Railways' topic page."""

from __future__ import annotations

from bs4 import BeautifulSoup

from scripts.discover.candidate import Candidate

# Selectors chosen to survive minor layout edits; update alongside the
# fixture if the site changes shape.
_LIST_SELECTOR = "ul.cyberattack-list li, ul li"
_DATE_SELECTOR = "span.date, time"
_LINK_SELECTOR = "a[href^='http']"
_SUMMARY_SELECTOR = "p"


def parse(html: str, *, discovered_at: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Candidate] = []
    for item in soup.select(_LIST_SELECTOR):
        link = item.select_one(_LINK_SELECTOR)
        if link is None:
            continue
        title = link.get_text(strip=True)
        url = link["href"]
        date_el = item.select_one(_DATE_SELECTOR)
        raw_date = date_el.get_text(strip=True) if date_el else None
        summary_el = item.select_one(_SUMMARY_SELECTOR)
        excerpt = summary_el.get_text(" ", strip=True) if summary_el else ""
        if not title or not url.startswith(("http://", "https://")):
            continue
        out.append(
            Candidate(
                url=url,
                title=title,
                raw_date=raw_date,
                source_id="konbriefing",
                source_type="news",
                lang="en",
                excerpt=excerpt[:500],
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(url: str, *, discovered_at: str, timeout_s: int = 15) -> list[Candidate]:
    import httpx

    resp = httpx.get(url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    return parse(resp.text, discovered_at=discovered_at)
```

- [ ] **Step 6: Run — confirm pass**

Run: `uv run pytest tests/discover/test_adapter_konbriefing.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/discover/adapters/ tests/discover/fixtures/konbriefing_sample.html tests/discover/test_adapter_konbriefing.py
git commit -m "feat(discover): konbriefing HTML adapter with fixture-based parse test"
```

---

## Task 8: EuRepoC adapter (JSON)

**Files:**
- Create: `scripts/discover/adapters/eurepoc.py`
- Create: `tests/discover/fixtures/eurepoc_sample.json`
- Test: `tests/discover/test_adapter_eurepoc.py`

- [ ] **Step 1: Create fixture**

Inspect the real EuRepoC endpoint first:

```bash
uv run python -c "import httpx,json; print(httpx.get('https://eurepoc.eu/api/incidents?sector=Transport').text[:1500])"
```

If the real endpoint is different from the planned URL, update `aggregators.yaml` accordingly and capture the real JSON shape.

Create `tests/discover/fixtures/eurepoc_sample.json` with two entries mirroring the real shape; if the real API is unreachable, use this representative shape:

```json
{
  "incidents": [
    {
      "id": "EuRepoC-2024-0321",
      "name": "Ransomware against DB Schenker",
      "date": "2024-03-01",
      "sector": "Transport",
      "subsector": "Rail",
      "countries": ["Germany"],
      "url": "https://eurepoc.eu/incident/2024-0321",
      "summary": "Rail freight operator hit by ransomware..."
    },
    {
      "id": "EuRepoC-2023-0818",
      "name": "Metro Paris cyber incident",
      "date": "2023-08-14",
      "sector": "Transport",
      "subsector": "Public transit",
      "countries": ["France"],
      "url": "https://eurepoc.eu/incident/2023-0818",
      "summary": "Network disruption reported..."
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/discover/test_adapter_eurepoc.py`:

```python
import json
from pathlib import Path

from scripts.discover.adapters.eurepoc import parse

FIXTURE = Path(__file__).parent / "fixtures" / "eurepoc_sample.json"


def test_parse_returns_two_rail_candidates():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    candidates = parse(payload, discovered_at="2026-04-19")
    assert len(candidates) == 2
    ids = [c.source_id for c in candidates]
    assert ids == ["eurepoc", "eurepoc"]
    assert candidates[0].raw_date == "2024-03-01"
    assert "db schenker" in candidates[0].title.lower()
```

- [ ] **Step 3: Run — confirm failure**

Run: `uv run pytest tests/discover/test_adapter_eurepoc.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement**

Create `scripts/discover/adapters/eurepoc.py`:

```python
"""EuRepoC adapter — Transport-sector filter over the public API."""

from __future__ import annotations

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail


def parse(payload: dict, *, discovered_at: str) -> list[Candidate]:
    kws = load_rail_keywords()
    out: list[Candidate] = []
    for entry in payload.get("incidents", []):
        subsector = entry.get("subsector", "")
        summary = entry.get("summary", "") or ""
        name = entry.get("name", "") or ""
        # Filter: EuRepoC Transport is broader than rail; keep only rail-adjacent.
        hay = f"{subsector} {name} {summary}"
        if not matches_rail(hay, kws):
            continue
        url = entry.get("url")
        if not url or not url.startswith(("http://", "https://")):
            continue
        out.append(
            Candidate(
                url=url,
                title=name,
                raw_date=entry.get("date"),
                source_id="eurepoc",
                source_type="database",
                lang="en",
                excerpt=summary[:500],
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(url: str, *, discovered_at: str, timeout_s: int = 20) -> list[Candidate]:
    import httpx

    resp = httpx.get(url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    return parse(resp.json(), discovered_at=discovered_at)
```

- [ ] **Step 5: Run — confirm pass**

Run: `uv run pytest tests/discover/test_adapter_eurepoc.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/discover/adapters/eurepoc.py tests/discover/fixtures/eurepoc_sample.json tests/discover/test_adapter_eurepoc.py
git commit -m "feat(discover): EuRepoC JSON adapter with rail-keyword filter"
```

---

## Task 9: ransomware.live adapter (JSON)

**Files:**
- Create: `scripts/discover/adapters/ransomware_live.py`
- Create: `tests/discover/fixtures/ransomware_live_sample.json`
- Test: `tests/discover/test_adapter_ransomware_live.py`

- [ ] **Step 1: Create fixture**

Inspect the live feed:

```bash
uv run python -c "import httpx; print(httpx.get('https://api.ransomware.live/v2/recentvictims').text[:1500])"
```

If the shape differs, update `aggregators.yaml` and the fixture.

Representative shape for `tests/discover/fixtures/ransomware_live_sample.json`:

```json
[
  {
    "victim": "DB Schenker",
    "group": "lockbit",
    "discovered": "2024-03-01T10:00:00Z",
    "post_url": "https://ransomware.live/posts/2024-03-01-db-schenker",
    "description": "Rail freight operator listed on leak site"
  },
  {
    "victim": "ACME Bakery",
    "group": "lockbit",
    "discovered": "2024-03-02T11:00:00Z",
    "post_url": "https://ransomware.live/posts/2024-03-02-acme",
    "description": "Bakery listed on leak site"
  }
]
```

- [ ] **Step 2: Write the failing test**

Create `tests/discover/test_adapter_ransomware_live.py`:

```python
import json
from pathlib import Path

from scripts.discover.adapters.ransomware_live import parse

FIXTURE = Path(__file__).parent / "fixtures" / "ransomware_live_sample.json"


def test_parse_keeps_rail_victim_drops_bakery():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    candidates = parse(payload, discovered_at="2026-04-19")
    assert len(candidates) == 1
    c = candidates[0]
    assert "db schenker" in c.title.lower()
    assert c.source_id == "ransomware_live"
    assert c.source_type == "leak_site"
    assert c.raw_date == "2024-03-01"
```

- [ ] **Step 3: Run — confirm failure**

Run: `uv run pytest tests/discover/test_adapter_ransomware_live.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement**

Create `scripts/discover/adapters/ransomware_live.py`:

```python
"""ransomware.live adapter — victims feed filtered by rail keywords."""

from __future__ import annotations

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail


def parse(payload: list[dict], *, discovered_at: str) -> list[Candidate]:
    kws = load_rail_keywords()
    out: list[Candidate] = []
    for entry in payload:
        victim = entry.get("victim", "")
        description = entry.get("description", "") or ""
        hay = f"{victim} {description}"
        if not matches_rail(hay, kws):
            continue
        url = entry.get("post_url")
        if not url or not url.startswith(("http://", "https://")):
            continue
        raw_date = (entry.get("discovered") or "")[:10] or None
        title = f"{victim} — leak-site listing ({entry.get('group', 'unknown group')})"
        excerpt = description[:500]
        out.append(
            Candidate(
                url=url,
                title=title,
                raw_date=raw_date,
                source_id="ransomware_live",
                source_type="leak_site",
                lang="en",
                excerpt=excerpt,
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(url: str, *, discovered_at: str, timeout_s: int = 20) -> list[Candidate]:
    import httpx

    resp = httpx.get(url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    return parse(resp.json(), discovered_at=discovered_at)
```

- [ ] **Step 5: Run — confirm pass**

Run: `uv run pytest tests/discover/test_adapter_ransomware_live.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/discover/adapters/ransomware_live.py tests/discover/fixtures/ransomware_live_sample.json tests/discover/test_adapter_ransomware_live.py
git commit -m "feat(discover): ransomware.live adapter with rail-keyword victim filter"
```

---

## Task 10: ENISA PDF adapter (text input, fetch wrapper does PDF)

**Files:**
- Create: `scripts/discover/adapters/enisa.py`
- Create: `tests/discover/fixtures/enisa_sample.txt`
- Test: `tests/discover/test_adapter_enisa.py`

Design note: `parse(text, pdf_url, *, discovered_at)` takes pre-extracted text so fixtures stay text-only. `fetch(pdf_url, *, discovered_at)` downloads + runs `pypdf` → calls `parse`.

- [ ] **Step 1: Create a text fixture**

`tests/discover/fixtures/enisa_sample.txt`:

```
ENISA Threat Landscape: Transport Sector
Reporting period: April 2023 – March 2024

In August 2023, a railway operator in Germany reported disruption
following a ransomware incident attributed to an unnamed actor.
Source: public disclosure by the operator.

Separate from that, a port operator in Rotterdam experienced a
phishing-driven breach in November 2023.

The Paris metro operator confirmed a cyber incident in July 2023.
```

- [ ] **Step 2: Write the failing test**

Create `tests/discover/test_adapter_enisa.py`:

```python
from pathlib import Path

from scripts.discover.adapters.enisa import parse

FIXTURE = Path(__file__).parent / "fixtures" / "enisa_sample.txt"


def test_parse_keeps_rail_paragraphs_drops_port():
    text = FIXTURE.read_text(encoding="utf-8")
    pdf_url = "https://www.enisa.europa.eu/publications/threat-landscape-transport-2024/@@download/fullReport"
    candidates = parse(text, pdf_url=pdf_url, discovered_at="2026-04-19")
    titles = [c.title.lower() for c in candidates]
    assert any("germany" in t and "railway" in t for t in titles)
    assert any("metro" in t for t in titles)
    assert not any("port" in t or "rotterdam" in t for t in titles)
    for c in candidates:
        assert c.source_id == "enisa_transport"
        assert c.source_type == "advisory"
        assert c.url == pdf_url
```

- [ ] **Step 3: Run — confirm failure**

Run: `uv run pytest tests/discover/test_adapter_enisa.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement**

Create `scripts/discover/adapters/enisa.py`:

```python
"""ENISA Transport Threat Landscape PDF adapter.

PDF text is pre-extracted by the fetch wrapper; `parse` is pure and
operates on paragraphs split by blank lines. One candidate per paragraph
that contains at least one rail keyword.
"""

from __future__ import annotations

import re

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail

_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _month_year_to_iso(para: str) -> str | None:
    m = _DATE_RE.search(para)
    if not m:
        return None
    month = _MONTHS[m.group(1).lower()]
    return f"{m.group(2)}-{month}"


def parse(text: str, *, pdf_url: str, discovered_at: str) -> list[Candidate]:
    kws = load_rail_keywords()
    out: list[Candidate] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for idx, para in enumerate(paragraphs):
        if not matches_rail(para, kws):
            continue
        raw_date = _month_year_to_iso(para)
        title = para.split(".")[0][:120]
        out.append(
            Candidate(
                url=pdf_url,
                title=title,
                raw_date=raw_date,
                source_id="enisa_transport",
                source_type="advisory",
                lang="en",
                excerpt=para[:500],
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(pdf_url: str, *, discovered_at: str, timeout_s: int = 30) -> list[Candidate]:
    import httpx
    import pypdf
    import io

    resp = httpx.get(pdf_url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
    return parse(text, pdf_url=pdf_url, discovered_at=discovered_at)
```

- [ ] **Step 5: Run — confirm pass**

Run: `uv run pytest tests/discover/test_adapter_enisa.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/discover/adapters/enisa.py tests/discover/fixtures/enisa_sample.txt tests/discover/test_adapter_enisa.py
git commit -m "feat(discover): ENISA PDF adapter (text-in, paragraph-level rail filter)"
```

---

## Task 11: BSI Lagebericht adapter (German, PDF)

**Files:**
- Create: `scripts/discover/adapters/bsi.py`
- Create: `tests/discover/fixtures/bsi_sample.txt`
- Test: `tests/discover/test_adapter_bsi.py`

Reuses the ENISA pattern with language-specific tweaks (German date regex). The rail keyword list already contains `Deutsche Bahn`, `DB Schenker` etc. Adapter marks `lang="de"`.

- [ ] **Step 1: Create a text fixture**

`tests/discover/fixtures/bsi_sample.txt`:

```
BSI Lagebericht 2024

Im August 2023 wurde bei der Deutschen Bahn ein IT-Vorfall bekannt,
der zu Einschränkungen im Fahrgastbetrieb führte. Die Ursache war
ein Ransomware-Angriff.

Unabhängig davon meldete ein Energieversorger im Mai 2023 einen
Phishing-Vorfall.
```

- [ ] **Step 2: Write the failing test**

Create `tests/discover/test_adapter_bsi.py`:

```python
from pathlib import Path

from scripts.discover.adapters.bsi import parse

FIXTURE = Path(__file__).parent / "fixtures" / "bsi_sample.txt"


def test_parse_keeps_db_paragraph_drops_energy():
    text = FIXTURE.read_text(encoding="utf-8")
    pdf_url = "https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Publikationen/Lageberichte/Lagebericht2024.pdf"
    candidates = parse(text, pdf_url=pdf_url, discovered_at="2026-04-19")
    titles = [c.title.lower() for c in candidates]
    assert any("deutschen bahn" in t or "deutsche bahn" in t for t in titles)
    assert not any("energieversorger" in t for t in titles)
    for c in candidates:
        assert c.lang == "de"
        assert c.source_id == "bsi_lagebericht"
```

- [ ] **Step 3: Run — confirm failure**

Run: `uv run pytest tests/discover/test_adapter_bsi.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement**

Create `scripts/discover/adapters/bsi.py`:

```python
"""BSI Lagebericht PDF adapter — German-language text, same shape as ENISA."""

from __future__ import annotations

import re

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail

_DE_DATE_RE = re.compile(
    r"\b(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b",
    re.IGNORECASE,
)
_DE_MONTHS = {
    "januar": "01", "februar": "02", "märz": "03", "april": "04",
    "mai": "05", "juni": "06", "juli": "07", "august": "08",
    "september": "09", "oktober": "10", "november": "11", "dezember": "12",
}


def _de_month_year_to_iso(para: str) -> str | None:
    m = _DE_DATE_RE.search(para)
    if not m:
        return None
    return f"{m.group(2)}-{_DE_MONTHS[m.group(1).lower()]}"


def parse(text: str, *, pdf_url: str, discovered_at: str) -> list[Candidate]:
    kws = load_rail_keywords()
    out: list[Candidate] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for para in paragraphs:
        if not matches_rail(para, kws):
            continue
        raw_date = _de_month_year_to_iso(para)
        title = para.split(".")[0][:120]
        out.append(
            Candidate(
                url=pdf_url,
                title=title,
                raw_date=raw_date,
                source_id="bsi_lagebericht",
                source_type="advisory",
                lang="de",
                excerpt=para[:500],
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(pdf_url: str, *, discovered_at: str, timeout_s: int = 30) -> list[Candidate]:
    import httpx
    import pypdf
    import io

    resp = httpx.get(pdf_url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
    return parse(text, pdf_url=pdf_url, discovered_at=discovered_at)
```

- [ ] **Step 5: Run — confirm pass**

Run: `uv run pytest tests/discover/test_adapter_bsi.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/discover/adapters/bsi.py tests/discover/fixtures/bsi_sample.txt tests/discover/test_adapter_bsi.py
git commit -m "feat(discover): BSI Lagebericht PDF adapter (German, paragraph-level)"
```

---

## Task 12: Stage 1 orchestrator — fetch_candidates.py

**Files:**
- Create: `scripts/fetch_candidates.py`
- Test: `tests/discover/test_fetch_orchestrator.py`

Responsibilities: load `aggregators.yaml`, call each enabled adapter's `fetch()`, catch per-adapter errors and continue, write `dist/candidates.json`.

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_fetch_orchestrator.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch

from scripts.discover.candidate import Candidate


def _make_candidates(source_id, n):
    return [
        Candidate(
            url=f"https://example.org/{source_id}/{i}",
            title=f"{source_id} hit {i}",
            raw_date="2024-01-01",
            source_id=source_id,
            source_type="news",
            lang="en",
            excerpt="",
            discovered_at="2026-04-19",
        )
        for i in range(n)
    ]


def test_orchestrator_calls_each_enabled_adapter_and_writes_json(tmp_path, monkeypatch):
    from scripts import fetch_candidates

    def _fake_konb(url, *, discovered_at, timeout_s=15):
        return _make_candidates("konbriefing", 2)

    def _fake_eurepoc(url, *, discovered_at, timeout_s=20):
        return _make_candidates("eurepoc", 1)

    def _fake_rl(url, *, discovered_at, timeout_s=20):
        raise RuntimeError("ransomware.live unreachable")

    monkeypatch.setattr("scripts.discover.adapters.konbriefing.fetch", _fake_konb)
    monkeypatch.setattr("scripts.discover.adapters.eurepoc.fetch", _fake_eurepoc)
    monkeypatch.setattr("scripts.discover.adapters.ransomware_live.fetch", _fake_rl)
    monkeypatch.setattr("scripts.discover.adapters.enisa.fetch",
                        lambda url, *, discovered_at, timeout_s=30: [])
    monkeypatch.setattr("scripts.discover.adapters.bsi.fetch",
                        lambda url, *, discovered_at, timeout_s=30: [])

    out_path = tmp_path / "candidates.json"
    summary = fetch_candidates.run(output_path=out_path, discovered_at="2026-04-19")

    data = json.loads(out_path.read_text())
    assert len(data) == 3
    ids = sorted({c["source_id"] for c in data})
    assert ids == ["eurepoc", "konbriefing"]
    # Failed adapter is reported, not raised:
    assert summary["errors"] == [{"aggregator": "ransomware_live", "error": "ransomware.live unreachable"}]
    assert summary["fetched"] == 3
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_fetch_orchestrator.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `scripts/fetch_candidates.py`:

```python
"""Stage 1 — deterministic fetch of all enabled aggregators to candidates.json."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from scripts.discover.adapters import bsi, enisa, eurepoc, konbriefing, ransomware_live
from scripts.discover.aggregators_config import AggregatorConfig, load_aggregators

LOG = logging.getLogger("discover.fetch")

_ADAPTERS = {
    "konbriefing": konbriefing.fetch,
    "eurepoc": eurepoc.fetch,
    "ransomware_live": ransomware_live.fetch,
    "enisa_transport": enisa.fetch,
    "bsi_lagebericht": bsi.fetch,
}


def _inputs_for(agg: AggregatorConfig) -> list[str]:
    if agg.kind == "pdf":
        return list(agg.pdfs)
    return [agg.url] if agg.url else []


def run(*, output_path: Path, discovered_at: str | None = None) -> dict:
    discovered_at = discovered_at or date.today().isoformat()
    all_candidates: list[dict] = []
    errors: list[dict] = []
    for agg in load_aggregators():
        if not agg.enabled:
            continue
        fetch_fn = _ADAPTERS.get(agg.id)
        if fetch_fn is None:
            errors.append({"aggregator": agg.id, "error": "no adapter registered"})
            continue
        for src in _inputs_for(agg):
            try:
                cands = fetch_fn(src, discovered_at=discovered_at)
                all_candidates.extend(c.to_dict() for c in cands)
                LOG.info("%s: %d candidates from %s", agg.id, len(cands), src)
            except Exception as e:  # adapter isolation — one bad source doesn't kill the run
                errors.append({"aggregator": agg.id, "error": str(e)})
                LOG.warning("%s fetch failed: %s", agg.id, e)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(all_candidates, indent=2, ensure_ascii=False))
    return {"fetched": len(all_candidates), "errors": errors}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="dist/candidates.json")
    args = ap.parse_args()
    summary = run(output_path=Path(args.output))
    print(
        f"fetched: {summary['fetched']} candidates; "
        f"errors: {len(summary['errors'])}"
    )
    for e in summary["errors"]:
        print(f"  [{e['aggregator']}] {e['error']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_fetch_orchestrator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_candidates.py tests/discover/test_fetch_orchestrator.py
git commit -m "feat(discover): Stage 1 orchestrator with per-adapter error isolation"
```

---

## Task 13: Pass 1 — classify module

**Files:**
- Create: `scripts/discover/classify.py`
- Test: `tests/discover/test_classify.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_classify.py`:

```python
from unittest.mock import patch

from scripts.discover.candidate import Candidate
from scripts.discover.classify import classify


def _c(title="Rail hit", excerpt="Ransomware at rail operator"):
    return Candidate(
        url="https://example.org/x",
        title=title,
        raw_date="2024-01-01",
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt=excerpt,
        discovered_at="2026-04-19",
    )


def test_classify_keeps_rail_cyber_above_threshold():
    with patch(
        "scripts.discover.classify.call_haiku_json",
        return_value=({"is_rail_cyber": True, "confidence": 0.9, "reason": "rail+ransomware"}, {"cost_usd": 0.001}),
    ):
        verdict, meta = classify(_c())
    assert verdict.is_rail_cyber is True
    assert verdict.kept is True
    assert meta["cost_usd"] == 0.001


def test_classify_drops_below_confidence_floor():
    with patch(
        "scripts.discover.classify.call_haiku_json",
        return_value=({"is_rail_cyber": True, "confidence": 0.4, "reason": "weak"}, {"cost_usd": 0.001}),
    ):
        verdict, _ = classify(_c())
    assert verdict.kept is False


def test_classify_drops_not_rail_cyber():
    with patch(
        "scripts.discover.classify.call_haiku_json",
        return_value=({"is_rail_cyber": False, "confidence": 0.9, "reason": "physical sabotage"}, {"cost_usd": 0.001}),
    ):
        verdict, _ = classify(_c(title="Train derailment"))
    assert verdict.kept is False


def test_classify_prompt_includes_title_and_excerpt():
    captured = {}

    def _fake(prompt, **kwargs):
        captured["prompt"] = prompt
        return ({"is_rail_cyber": True, "confidence": 0.9, "reason": "ok"}, {"cost_usd": 0.001})

    with patch("scripts.discover.classify.call_haiku_json", side_effect=_fake):
        classify(_c(title="DB Schenker hit", excerpt="Ransomware attack..."))
    assert "DB Schenker hit" in captured["prompt"]
    assert "Ransomware attack" in captured["prompt"]
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_classify.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `scripts/discover/classify.py`:

```python
"""Pass 1 — classify a candidate as a rail cyber incident or drop it."""

from __future__ import annotations

from dataclasses import dataclass

from scripts.discover.candidate import Candidate
from scripts.discover.llm import call_haiku_json

CONFIDENCE_FLOOR = 0.6

PROMPT_TEMPLATE = """\
You are classifying whether a short news item describes a cyber incident
affecting a railway, metro, train, or rail-adjacent operator.

Answer with JSON ONLY, no prose. Schema:
{{"is_rail_cyber": boolean, "confidence": number between 0 and 1, "reason": "<=20 words"}}

Return is_rail_cyber=true only when BOTH hold:
- The incident is clearly cyber (ransomware, intrusion, phishing, wiper, DDoS, data breach, ICS compromise).
- The target is clearly rail/metro/transit — not a general transport company unless the rail arm is named.

Physical sabotage, cable theft, accidents, and unrelated IT outages => false.

Title: {title}
Excerpt: {excerpt}
"""


@dataclass(frozen=True)
class ClassifyVerdict:
    is_rail_cyber: bool
    confidence: float
    reason: str
    kept: bool


def classify(c: Candidate) -> tuple[ClassifyVerdict, dict]:
    prompt = PROMPT_TEMPLATE.format(title=c.title, excerpt=c.excerpt or "(no excerpt available)")
    parsed, meta = call_haiku_json(prompt)
    is_rc = bool(parsed.get("is_rail_cyber", False))
    conf = float(parsed.get("confidence", 0.0))
    reason = str(parsed.get("reason", ""))[:200]
    kept = is_rc and conf >= CONFIDENCE_FLOOR
    return ClassifyVerdict(is_rc, conf, reason, kept), meta
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_classify.py -v`
Expected: all four tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/classify.py tests/discover/test_classify.py
git commit -m "feat(discover): Pass 1 classifier (rail+cyber) with 0.6 confidence floor"
```

---

## Task 14: Pass 2 — dedup module (deterministic + Haiku tiebreak)

**Files:**
- Create: `scripts/discover/dedup.py`
- Create: `tests/discover/fixtures/incidents/2021-07-22_death-kitty.yaml`
- Create: `tests/discover/fixtures/incidents/2017-05-13_wannacry.yaml`
- Test: `tests/discover/test_dedup.py`

- [ ] **Step 1: Create two synthetic existing-incident fixtures**

`tests/discover/fixtures/incidents/2021-07-22_death-kitty.yaml`:

```yaml
id: 2021-07-22_death-kitty
schema_version: "1.0"
event_date: 2021-07-22
event_date_precision: day
countries_impacted: [IR]
target_organization: Iranian Railways
confirmation_status: reported
description_en: >
  Wiper attack against Iranian Railways display boards.
sources:
  - url: https://example.org/death-kitty-original
    type: news
last_updated: 2021-07-30
```

`tests/discover/fixtures/incidents/2017-05-13_wannacry.yaml`:

```yaml
id: 2017-05-13_wannacry
schema_version: "1.0"
event_date: 2017-05-13
event_date_precision: day
countries_impacted: [DE]
target_organization: Deutsche Bahn
confirmation_status: confirmed
description_en: >
  WannaCry affected Deutsche Bahn display boards.
sources:
  - url: https://example.org/wannacry-db
    type: news
last_updated: 2021-07-30
```

- [ ] **Step 2: Write the failing test**

Create `tests/discover/test_dedup.py`:

```python
from pathlib import Path
from unittest.mock import patch

from scripts.discover.candidate import Candidate
from scripts.discover.dedup import DedupResult, dedup

FIXTURES = Path(__file__).parent / "fixtures" / "incidents"


def _cand(url="https://new.example.org/x", title="", raw_date="2017-05-14"):
    return Candidate(
        url=url,
        title=title,
        raw_date=raw_date,
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt="",
        discovered_at="2026-04-19",
    )


def test_exact_url_hit_drops_without_llm():
    c = _cand(url="https://example.org/wannacry-db")
    with patch("scripts.discover.dedup.call_haiku_json") as m:
        result = dedup(c, incidents_dir=FIXTURES)
    assert result.duplicate_of == "2017-05-13_wannacry"
    assert result.kept is False
    assert result.used_llm is False
    m.assert_not_called()


def test_no_match_passes_through_without_llm():
    c = _cand(url="https://new.example.org/unrelated", title="totally unrelated",
              raw_date="2024-02-02")
    with patch("scripts.discover.dedup.call_haiku_json") as m:
        result = dedup(c, incidents_dir=FIXTURES)
    assert result.duplicate_of is None
    assert result.kept is True
    assert result.used_llm is False
    m.assert_not_called()


def test_near_date_same_org_triggers_llm_and_drops():
    c = _cand(title="WannaCry hits Deutsche Bahn display boards", raw_date="2017-05-14")
    with patch(
        "scripts.discover.dedup.call_haiku_json",
        return_value=({"duplicate_of": "2017-05-13_wannacry", "reason": "same event"}, {"cost_usd": 0.002}),
    ) as m:
        result = dedup(c, incidents_dir=FIXTURES)
    m.assert_called_once()
    assert result.duplicate_of == "2017-05-13_wannacry"
    assert result.kept is False
    assert result.used_llm is True


def test_near_date_llm_says_not_duplicate_keeps():
    c = _cand(title="Deutsche Bahn unrelated outage", raw_date="2017-05-14")
    with patch(
        "scripts.discover.dedup.call_haiku_json",
        return_value=({"duplicate_of": None, "reason": "different event"}, {"cost_usd": 0.002}),
    ):
        result = dedup(c, incidents_dir=FIXTURES)
    assert result.duplicate_of is None
    assert result.kept is True
    assert result.used_llm is True
```

- [ ] **Step 3: Run — confirm failure**

Run: `uv run pytest tests/discover/test_dedup.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement**

Create `scripts/discover/dedup.py`:

```python
"""Pass 2 — dedup against existing incidents. Deterministic first, Haiku on ambiguity."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from scripts.discover.candidate import Candidate
from scripts.discover.llm import call_haiku_json

DATE_WINDOW_DAYS = 7
JACCARD_FLOOR = 0.5

_DEFAULT_INCIDENTS_DIR = Path(__file__).resolve().parents[2] / "incidents"


@dataclass(frozen=True)
class _Existing:
    id: str
    event_date: date | None
    urls: frozenset[str]
    tokens: frozenset[str]
    description_en: str


@dataclass(frozen=True)
class DedupResult:
    duplicate_of: str | None
    reason: str
    kept: bool
    used_llm: bool
    meta: dict | None = None


def _tokens(*parts: str) -> frozenset[str]:
    joined = " ".join(p.lower() for p in parts if p)
    return frozenset(t for t in re.split(r"\W+", joined) if len(t) >= 3)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _parse_iso(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


@lru_cache(maxsize=16)
def _load_existing(incidents_dir: Path) -> tuple[_Existing, ...]:
    out: list[_Existing] = []
    for path in sorted(incidents_dir.glob("*.yaml")):
        if path.name == "TEMPLATE.yaml":
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        urls = frozenset(
            (s or {}).get("url", "") for s in (doc.get("sources") or [])
            if isinstance(s, dict) and s.get("url")
        )
        tokens = _tokens(doc.get("target_organization") or "",
                         doc.get("description_en") or "")
        out.append(
            _Existing(
                id=str(doc.get("id", path.stem)),
                event_date=_parse_iso(str(doc.get("event_date") or "")),
                urls=urls,
                tokens=tokens,
                description_en=str(doc.get("description_en") or ""),
            )
        )
    return tuple(out)


DEDUP_PROMPT = """\
You are deciding whether a newly-discovered candidate is the SAME incident
as any of the existing incidents below. Answer JSON ONLY:
{{"duplicate_of": "<incident id>" | null, "reason": "<=20 words"}}

Candidate:
  title: {title}
  date: {date}
  url: {url}
  excerpt: {excerpt}

Possibly matching existing incidents:
{existing}
"""


def _render_existing(e: _Existing) -> str:
    return f"- id: {e.id}\n  date: {e.event_date}\n  description: {e.description_en[:300]}"


def dedup(c: Candidate, *, incidents_dir: Path = _DEFAULT_INCIDENTS_DIR) -> DedupResult:
    existing = _load_existing(incidents_dir)

    # Exact URL match
    for e in existing:
        if c.url in e.urls:
            return DedupResult(e.id, "exact URL match", kept=False, used_llm=False)

    cand_date = _parse_iso(c.raw_date)
    cand_tokens = _tokens(c.title, c.excerpt)

    ambiguous: list[_Existing] = []
    for e in existing:
        if not cand_date or not e.event_date:
            continue
        if abs((cand_date - e.event_date).days) > DATE_WINDOW_DAYS:
            continue
        if _jaccard(cand_tokens, e.tokens) >= JACCARD_FLOOR:
            ambiguous.append(e)

    if not ambiguous:
        return DedupResult(None, "no match", kept=True, used_llm=False)

    rendered = "\n".join(_render_existing(e) for e in ambiguous[:3])
    prompt = DEDUP_PROMPT.format(
        title=c.title,
        date=c.raw_date or "unknown",
        url=c.url,
        excerpt=(c.excerpt or "")[:500],
        existing=rendered,
    )
    parsed, meta = call_haiku_json(prompt)
    dup = parsed.get("duplicate_of")
    reason = str(parsed.get("reason", ""))[:200]
    if dup:
        return DedupResult(str(dup), reason, kept=False, used_llm=True, meta=meta)
    return DedupResult(None, reason or "llm says distinct", kept=True, used_llm=True, meta=meta)
```

- [ ] **Step 5: Run — confirm pass**

Run: `uv run pytest tests/discover/test_dedup.py -v`
Expected: all four tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/discover/dedup.py tests/discover/fixtures/incidents/ tests/discover/test_dedup.py
git commit -m "feat(discover): Pass 2 dedup (deterministic URL/date + Haiku ambiguity tiebreak)"
```

---

## Task 15: Pass 3 — extract module

**Files:**
- Create: `scripts/discover/extract.py`
- Test: `tests/discover/test_extract.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_extract.py`:

```python
from unittest.mock import patch

from scripts.discover.candidate import Candidate
from scripts.discover.extract import ExtractedFields, extract


def _c():
    return Candidate(
        url="https://example.org/x",
        title="DB Schenker hit",
        raw_date="2024-03-01",
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt="rail freight ransomware",
        discovered_at="2026-04-19",
    )


def test_extract_uses_article_body_when_available():
    def _fake_fetch(url, timeout_s=10):
        return "Long article body about DB Schenker in Germany on 2024-03-01."

    with patch(
        "scripts.discover.extract.call_haiku_json",
        return_value=(
            {
                "event_date": "2024-03-01",
                "event_date_precision": "day",
                "countries_impacted": ["DE"],
                "target_organization": "DB Schenker",
                "reported_date": None,
            },
            {"cost_usd": 0.002},
        ),
    ):
        with patch("scripts.discover.extract._fetch_article_text", side_effect=_fake_fetch):
            fields, meta = extract(_c())
    assert fields == ExtractedFields(
        event_date="2024-03-01",
        event_date_precision="day",
        countries_impacted=("DE",),
        target_organization="DB Schenker",
        reported_date=None,
    )


def test_extract_fails_open_on_fetch_error():
    def _raise(url, timeout_s=10):
        raise RuntimeError("network")

    with patch(
        "scripts.discover.extract.call_haiku_json",
        return_value=(
            {
                "event_date": "2024-03-01",
                "event_date_precision": "day",
                "countries_impacted": [],
                "target_organization": None,
                "reported_date": None,
            },
            {"cost_usd": 0.001},
        ),
    ):
        with patch("scripts.discover.extract._fetch_article_text", side_effect=_raise):
            fields, _ = extract(_c())
    assert fields.event_date == "2024-03-01"  # Haiku was still called with excerpt-only
    assert fields.countries_impacted == ()
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_extract.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `scripts/discover/extract.py`:

```python
"""Pass 3 — extract structured fields from the article body (or excerpt fallback)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.discover.candidate import Candidate
from scripts.discover.llm import call_haiku_json

PROMPT_TEMPLATE = """\
Extract facts from the text below. Return JSON ONLY, no prose:
{{
  "event_date": "YYYY-MM-DD" or null,
  "event_date_precision": "day" | "month" | "year",
  "countries_impacted": ["ISO-3166 alpha-2", ...],
  "target_organization": "string" or null,
  "reported_date": "YYYY-MM-DD" or null
}}

Rules:
- Prefer null over inventing a value.
- Use "day" precision only when a full date is explicit. "month" when only
  month+year is given. "year" when only the year is given.
- countries_impacted lists every country where the attack caused impact,
  ISO 3166-1 alpha-2 codes (DE, FR, IT, ...).
- target_organization is the primary victim if named; otherwise null.

Text:
{body}
"""


@dataclass(frozen=True)
class ExtractedFields:
    event_date: str | None
    event_date_precision: str
    countries_impacted: tuple[str, ...]
    target_organization: str | None
    reported_date: str | None


def _fetch_article_text(url: str, timeout_s: int = 10) -> str:
    import httpx
    from bs4 import BeautifulSoup

    resp = httpx.get(url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)[:8000]


def _as_tuple(v: Any) -> tuple[str, ...]:
    if not isinstance(v, list):
        return ()
    return tuple(str(x) for x in v if isinstance(x, str))


def extract(c: Candidate) -> tuple[ExtractedFields, dict]:
    try:
        body = _fetch_article_text(c.url)
    except Exception:
        body = c.excerpt or c.title
    prompt = PROMPT_TEMPLATE.format(body=body[:6000])
    parsed, meta = call_haiku_json(prompt)
    return (
        ExtractedFields(
            event_date=(parsed.get("event_date") or None),
            event_date_precision=str(parsed.get("event_date_precision") or "day"),
            countries_impacted=_as_tuple(parsed.get("countries_impacted")),
            target_organization=(parsed.get("target_organization") or None),
            reported_date=(parsed.get("reported_date") or None),
        ),
        meta,
    )
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_extract.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/extract.py tests/discover/test_extract.py
git commit -m "feat(discover): Pass 3 extractor (fetches article body, falls back to excerpt)"
```

---

## Task 16: Pass 4 — summarize module

**Files:**
- Create: `scripts/discover/summarize.py`
- Test: `tests/discover/test_summarize.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_summarize.py`:

```python
from unittest.mock import patch

from scripts.discover.candidate import Candidate
from scripts.discover.summarize import summarize


def _c(lang="en", excerpt="Some excerpt"):
    return Candidate(
        url="https://example.org/x",
        title="t",
        raw_date=None,
        source_id="konbriefing",
        source_type="news",
        lang=lang,
        excerpt=excerpt,
        discovered_at="2026-04-19",
    )


def test_summarize_returns_en_for_english_source():
    with patch(
        "scripts.discover.summarize.call_haiku_json",
        return_value=({"description_en": "One sentence.", "description_de": None}, {"cost_usd": 0.002}),
    ):
        result, _ = summarize(_c(lang="en"))
    assert result.description_en == "One sentence."
    assert result.description_de is None


def test_summarize_returns_both_for_german_source():
    with patch(
        "scripts.discover.summarize.call_haiku_json",
        return_value=(
            {"description_en": "English translation.", "description_de": "Deutscher Originaltext."},
            {"cost_usd": 0.003},
        ),
    ):
        result, _ = summarize(_c(lang="de", excerpt="Deutsch..."))
    assert result.description_en == "English translation."
    assert result.description_de == "Deutscher Originaltext."
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_summarize.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `scripts/discover/summarize.py`:

```python
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
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_summarize.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/summarize.py tests/discover/test_summarize.py
git commit -m "feat(discover): Pass 4 summarizer (English + optional German original)"
```

---

## Task 17: Stub writer

**Files:**
- Create: `scripts/discover/stub_writer.py`
- Test: `tests/discover/test_stub_writer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_stub_writer.py`:

```python
from pathlib import Path

import yaml

from scripts.discover.candidate import Candidate
from scripts.discover.classify import ClassifyVerdict
from scripts.discover.extract import ExtractedFields
from scripts.discover.stub_writer import write_stub
from scripts.discover.summarize import SummaryResult


def _c():
    return Candidate(
        url="https://konbriefing.com/x",
        title="DB Schenker ransomware",
        raw_date="2024-03-01",
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt="rail freight",
        discovered_at="2026-04-19",
    )


def _en_inputs():
    return (
        ClassifyVerdict(True, 0.82, "rail+ransomware", True),
        ExtractedFields("2024-03-01", "day", ("DE",), "DB Schenker", None),
        SummaryResult("Rail freight operator hit by ransomware.", None),
    )


def test_stub_filename_matches_id_field(tmp_path):
    verdict, fields, summary = _en_inputs()
    path = write_stub(_c(), verdict, fields, summary, drafts_dir=tmp_path)
    assert path.parent == tmp_path
    assert path.suffix == ".yaml"
    doc = yaml.safe_load(path.read_text())
    assert doc["id"] == path.stem
    assert doc["id"].startswith("2024-03-01_")


def test_stub_marks_needs_review_and_null_enums(tmp_path):
    verdict, fields, summary = _en_inputs()
    path = write_stub(_c(), verdict, fields, summary, drafts_dir=tmp_path)
    doc = yaml.safe_load(path.read_text())
    assert doc["provenance"]["needs_review"] is True
    assert doc["provenance"]["discovered_by"] == "discover_incidents"
    assert doc["provenance"]["aggregator"] == "konbriefing"
    assert doc["provenance"]["haiku_classify_confidence"] == 0.82
    for key in ("industry_sector", "operator_type", "attack_vector",
                "motive", "affected_systems", "malware", "threat_actor"):
        assert doc.get(key) is None
    assert doc["impact"]["scope"] is None


def test_stub_includes_source_with_absolute_url(tmp_path):
    verdict, fields, summary = _en_inputs()
    path = write_stub(_c(), verdict, fields, summary, drafts_dir=tmp_path)
    doc = yaml.safe_load(path.read_text())
    assert doc["sources"][0]["url"].startswith("https://")
    assert doc["sources"][0]["type"] == "news"
    assert doc["sources"][0]["language"] == "en"


def test_stub_has_all_required_top_level_keys(tmp_path):
    """Stub must carry every field validate.py requires, so promotion won't fail."""
    import subprocess
    import shutil

    # Copy fixture incidents + place stub alongside under a temp incidents/ root.
    incidents = tmp_path / "incidents"
    drafts = incidents / "drafts"
    incidents.mkdir()
    drafts.mkdir()
    # Minimal synthetic incident so validate has something to parse.
    (incidents / "2024-03-01_example.yaml").write_text(
        "id: 2024-03-01_example\nschema_version: \"1.0\"\nevent_date: 2024-03-01\n"
        "event_date_precision: day\ncountries_impacted: [DE]\nconfirmation_status: reported\n"
        "description_en: Test.\nsources:\n  - url: https://example.org/\n    type: news\n"
        "last_updated: 2024-03-01\n",
        encoding="utf-8",
    )
    verdict, fields, summary = _en_inputs()
    write_stub(_c(), verdict, fields, summary, drafts_dir=drafts)

    # We do NOT run scripts/validate.py here — that belongs to the later
    # drafts-exclusion regression test. Instead, assert the stub parses
    # as YAML and has required keys.
    path = next(drafts.glob("*.yaml"))
    doc = yaml.safe_load(path.read_text())
    for required in ("id", "schema_version", "event_date", "event_date_precision",
                     "countries_impacted", "confirmation_status", "description_en",
                     "sources", "last_updated"):
        assert required in doc and doc[required] is not None
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_stub_writer.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `scripts/discover/stub_writer.py`:

```python
"""Stub YAML writer. Produces incidents/drafts/<id>.yaml with needs_review: true."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

import yaml

from scripts.discover.candidate import Candidate
from scripts.discover.classify import ClassifyVerdict
from scripts.discover.extract import ExtractedFields
from scripts.discover.summarize import SummaryResult


_UMLAUT = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss",
                         "Ä": "a", "Ö": "o", "Ü": "u"})


def _slugify(s: str) -> str:
    s = s.translate(_UMLAUT).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or "unknown"


def _build_id(c: Candidate, fields: ExtractedFields) -> str:
    event_date = fields.event_date or (c.raw_date or date.today().isoformat())[:10]
    if fields.target_organization:
        slug = _slugify(fields.target_organization)
    else:
        h = hashlib.sha1(c.url.encode()).hexdigest()[:4]
        slug = f"{c.source_id}-{h}"
    return f"{event_date}_{slug}"


def _stub_dict(c: Candidate, verdict: ClassifyVerdict, fields: ExtractedFields,
               summary: SummaryResult, today: str) -> dict:
    incident_id = _build_id(c, fields)
    return {
        "id": incident_id,
        "schema_version": "1.0",
        "event_date": fields.event_date,
        "event_date_precision": fields.event_date_precision,
        "reported_date": fields.reported_date,
        "countries_impacted": list(fields.countries_impacted) or [],
        "region": None,
        "coordinates": None,
        "target_organization": fields.target_organization,
        "industry_sector": None,
        "operator_type": None,
        "attack_vector": None,
        "supply_chain": None,
        "malware": None,
        "extortion": None,
        "motive": None,
        "mitre_attack_techniques": None,
        "threat_actor": None,
        "threat_actor_country": None,
        "attribution_confidence": None,
        "confirmation_status": "reported",
        "affected_systems": None,
        "data_published": None,
        "impact": {
            "scope": None,
            "duration_hours": None,
            "magnitude": {
                "affected_trains": None,
                "affected_passengers": None,
                "monetary_damage_eur": None,
            },
            "data_compromise": {
                "intellectual_property": None,
                "organizational_data": None,
                "customer_data": None,
            },
        },
        "description_en": summary.description_en,
        "description_de": summary.description_de,
        "sources": [
            {
                "url": c.url,
                "type": c.source_type,
                "publisher": None,
                "published_date": None,
                "language": c.lang,
                "accessed_date": today,
            }
        ],
        "provenance": {
            "needs_review": True,
            "discovered_by": "discover_incidents",
            "aggregator": c.source_id,
            "haiku_classify_confidence": round(verdict.confidence, 2),
        },
        "contributors": ["discover_incidents"],
        "last_updated": today,
        "notes": None,
    }


def write_stub(
    c: Candidate,
    verdict: ClassifyVerdict,
    fields: ExtractedFields,
    summary: SummaryResult,
    *,
    drafts_dir: Path,
    today: str | None = None,
) -> Path:
    today = today or date.today().isoformat()
    doc = _stub_dict(c, verdict, fields, summary, today)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    out_path = drafts_dir / f"{doc['id']}.yaml"
    with out_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
    return out_path
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_stub_writer.py -v`
Expected: all four tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/discover/stub_writer.py tests/discover/test_stub_writer.py
git commit -m "feat(discover): stub writer (needs_review=true, null enums, full TEMPLATE shape)"
```

---

## Task 18: Stage 2 orchestrator — stub_candidates.py

**Files:**
- Create: `scripts/stub_candidates.py`
- Test: `tests/discover/test_stub_orchestrator.py`

Wires Passes 1–4 together, iterates over `candidates.json`, writes stubs, prints cost report, appends to `dist/.discover-cost.log`, honours `--max-cost`.

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_stub_orchestrator.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch

from scripts.discover.classify import ClassifyVerdict
from scripts.discover.extract import ExtractedFields
from scripts.discover.summarize import SummaryResult


def _candidate_dict(url, title, source_id="konbriefing"):
    return {
        "url": url, "title": title, "raw_date": "2024-03-01",
        "source_id": source_id, "source_type": "news", "lang": "en",
        "excerpt": "rail ransomware", "discovered_at": "2026-04-19",
    }


def test_orchestrator_writes_one_stub_per_kept_candidate(tmp_path):
    from scripts import stub_candidates

    candidates_path = tmp_path / "candidates.json"
    drafts_dir = tmp_path / "drafts"
    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir()
    candidates_path.write_text(json.dumps([
        _candidate_dict("https://a.example/1", "DB Schenker hit"),
        _candidate_dict("https://a.example/2", "train derailment"),
    ]))

    # classify: first kept, second dropped
    classify_out = iter([
        (ClassifyVerdict(True, 0.9, "ok", True), {"cost_usd": 0.001}),
        (ClassifyVerdict(False, 0.9, "physical", False), {"cost_usd": 0.001}),
    ])
    extract_out = (ExtractedFields("2024-03-01", "day", ("DE",), "DB Schenker", None),
                   {"cost_usd": 0.002})
    summary_out = (SummaryResult("Rail freight operator hit.", None), {"cost_usd": 0.002})

    with patch("scripts.stub_candidates.classify", side_effect=lambda c: next(classify_out)), \
         patch("scripts.stub_candidates.dedup", return_value=type("D", (), {
             "duplicate_of": None, "kept": True, "used_llm": False, "meta": None
         })()), \
         patch("scripts.stub_candidates.extract", return_value=extract_out), \
         patch("scripts.stub_candidates.summarize", return_value=summary_out):
        summary = stub_candidates.run(
            candidates_path=candidates_path,
            drafts_dir=drafts_dir,
            incidents_dir=incidents_dir,
            cost_log_path=tmp_path / ".cost.log",
        )

    stubs = list(drafts_dir.glob("*.yaml"))
    assert len(stubs) == 1
    assert summary["classified_kept"] == 1
    assert summary["dropped_classify"] == 1
    assert summary["stubs_written"] == 1
    assert summary["total_cost_usd"] > 0


def test_orchestrator_halts_on_max_cost(tmp_path):
    from scripts import stub_candidates

    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(json.dumps([
        _candidate_dict("https://a.example/1", "DB Schenker hit"),
        _candidate_dict("https://a.example/2", "SNCF hit"),
    ]))
    drafts_dir = tmp_path / "drafts"
    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir()

    with patch(
        "scripts.stub_candidates.classify",
        return_value=(ClassifyVerdict(True, 0.9, "ok", True), {"cost_usd": 10.0}),
    ), patch("scripts.stub_candidates.dedup", return_value=type("D", (), {
        "duplicate_of": None, "kept": True, "used_llm": False, "meta": None
    })()), patch("scripts.stub_candidates.extract", return_value=(
        ExtractedFields("2024-03-01", "day", ("DE",), "X", None), {"cost_usd": 0.0}
    )), patch("scripts.stub_candidates.summarize", return_value=(
        SummaryResult("x.", None), {"cost_usd": 0.0}
    )):
        summary = stub_candidates.run(
            candidates_path=candidates_path,
            drafts_dir=drafts_dir,
            incidents_dir=incidents_dir,
            cost_log_path=tmp_path / ".cost.log",
            max_cost_usd=1.0,
        )

    assert summary["halted_on_cost"] is True
    assert summary["stubs_written"] == 1
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_stub_orchestrator.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `scripts/stub_candidates.py`:

```python
"""Stage 2 — run Passes 1-4 over candidates.json, write stubs to incidents/drafts/."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from scripts.discover.candidate import Candidate
from scripts.discover.classify import classify
from scripts.discover.dedup import dedup
from scripts.discover.extract import extract
from scripts.discover.stub_writer import write_stub
from scripts.discover.summarize import summarize

LOG = logging.getLogger("discover.stub")


def _load_candidates(path: Path) -> list[Candidate]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Candidate.from_dict(d) for d in data]


def run(
    *,
    candidates_path: Path,
    drafts_dir: Path,
    incidents_dir: Path,
    cost_log_path: Path,
    max_cost_usd: float | None = None,
    today: str | None = None,
) -> dict:
    today = today or date.today().isoformat()
    candidates = _load_candidates(candidates_path)

    total_cost = 0.0
    classified_kept = dropped_classify = dropped_dedup = stubs = 0
    halted = False
    almost: list[dict] = []

    for c in candidates:
        verdict, meta = classify(c)
        total_cost += float(meta.get("cost_usd", 0.0))
        if not verdict.kept:
            dropped_classify += 1
            if 0.5 <= verdict.confidence < 0.6:
                almost.append({"url": c.url, "confidence": verdict.confidence, "title": c.title})
            if max_cost_usd is not None and total_cost >= max_cost_usd:
                halted = True; break
            continue
        classified_kept += 1

        dedup_res = dedup(c, incidents_dir=incidents_dir)
        if dedup_res.used_llm and dedup_res.meta:
            total_cost += float(dedup_res.meta.get("cost_usd", 0.0))
        if not dedup_res.kept:
            dropped_dedup += 1
            if max_cost_usd is not None and total_cost >= max_cost_usd:
                halted = True; break
            continue

        fields, meta = extract(c)
        total_cost += float(meta.get("cost_usd", 0.0))
        summary_res, meta = summarize(c)
        total_cost += float(meta.get("cost_usd", 0.0))

        write_stub(c, verdict, fields, summary_res, drafts_dir=drafts_dir, today=today)
        stubs += 1

        if max_cost_usd is not None and total_cost >= max_cost_usd:
            halted = True; break

    cost_log_path.parent.mkdir(parents=True, exist_ok=True)
    with cost_log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{today}\t{total_cost:.4f}\t{stubs} stubs\n")

    summary = {
        "fetched": len(candidates),
        "classified_kept": classified_kept,
        "dropped_classify": dropped_classify,
        "dropped_dedup": dropped_dedup,
        "stubs_written": stubs,
        "total_cost_usd": round(total_cost, 4),
        "halted_on_cost": halted,
        "almost_passed": almost[:5],
    }
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="dist/candidates.json")
    ap.add_argument("--drafts-dir", default="incidents/drafts")
    ap.add_argument("--incidents-dir", default="incidents")
    ap.add_argument("--cost-log", default="dist/.discover-cost.log")
    ap.add_argument("--max-cost", type=float, default=None)
    args = ap.parse_args()

    s = run(
        candidates_path=Path(args.candidates),
        drafts_dir=Path(args.drafts_dir),
        incidents_dir=Path(args.incidents_dir),
        cost_log_path=Path(args.cost_log),
        max_cost_usd=args.max_cost,
    )
    print(
        f"fetched: {s['fetched']} | kept: {s['classified_kept']} | "
        f"dropped: classify {s['dropped_classify']}, dedup {s['dropped_dedup']} | "
        f"stubs: {s['stubs_written']} | cost: ${s['total_cost_usd']:.4f}"
        + (" | HALTED ON COST" if s["halted_on_cost"] else "")
    )
    if s["almost_passed"]:
        print("almost-passed (review):")
        for a in s["almost_passed"]:
            print(f"  {a['confidence']:.2f}  {a['title']}  ({a['url']})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_stub_orchestrator.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/stub_candidates.py tests/discover/test_stub_orchestrator.py
git commit -m "feat(discover): Stage 2 orchestrator (4-pass loop, cost log, max-cost halt)"
```

---

## Task 19: Prompt snapshot tests

**Files:**
- Create: `tests/discover/fixtures/prompts/classify.txt`
- Create: `tests/discover/fixtures/prompts/dedup.txt`
- Create: `tests/discover/fixtures/prompts/extract.txt`
- Create: `tests/discover/fixtures/prompts/summarize.txt`
- Test: `tests/discover/test_prompts_snapshot.py`

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_prompts_snapshot.py`:

```python
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
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_prompts_snapshot.py -v`
Expected: FAIL with FileNotFoundError on snapshot files.

- [ ] **Step 3: Generate and commit the snapshots**

Run once:

```bash
mkdir -p tests/discover/fixtures/prompts
uv run python -c "
from scripts.discover.classify import PROMPT_TEMPLATE as C
from scripts.discover.dedup import _HAIKU_PROMPT as D
from scripts.discover.extract import PROMPT_TEMPLATE as E
from scripts.discover.summarize import PROMPT_TEMPLATE as S
from pathlib import Path
p = Path('tests/discover/fixtures/prompts')
(p/'classify.txt').write_text(C.format(title='<TITLE>', excerpt='<EXCERPT>'))
(p/'dedup.txt').write_text(D.format(title='<TITLE>', date='<DATE>', url='<URL>', excerpt='<EXCERPT>', existing='<EXISTING>'))
(p/'extract.txt').write_text(E.format(body='<BODY>'))
(p/'summarize.txt').write_text(S.format(title='<TITLE>', lang='<LANG>', body='<BODY>'))
print('snapshots written')
"
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_prompts_snapshot.py -v`
Expected: all four tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/discover/fixtures/prompts/ tests/discover/test_prompts_snapshot.py
git commit -m "test(discover): prompt snapshot tests (guard against accidental prompt edits)"
```

---

## Task 20: Drafts-exclusion regression tests

**Files:**
- Create: `tests/test_validate_excludes_drafts.py`
- Create: `tests/test_build_excludes_drafts.py`

The existing v0.2.0 release already has non-recursive globs; this task locks that in against the new `incidents/drafts/` directory.

- [ ] **Step 1: Inspect validate.py and build_release.py globs**

Run: `grep -n 'glob\|iterdir' scripts/validate.py scripts/build_release.py`
Confirm both use a non-recursive pattern (e.g. `incidents/*.yaml`, not `**/*.yaml`).

- [ ] **Step 2: Write the validate regression test**

Create `tests/test_validate_excludes_drafts.py`:

```python
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
```

- [ ] **Step 3: Write the build regression test**

Create `tests/test_build_excludes_drafts.py`:

```python
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
```

- [ ] **Step 4: Run both**

Run: `uv run pytest tests/test_validate_excludes_drafts.py tests/test_build_excludes_drafts.py -v`
Expected: PASS. If either fails, the fix is in `scripts/validate.py` / `scripts/build_release.py` to switch from recursive to `incidents/*.yaml` glob — update the script, re-run.

- [ ] **Step 5: Commit**

```bash
git add tests/test_validate_excludes_drafts.py tests/test_build_excludes_drafts.py
# and any script fixes if made
git add scripts/validate.py scripts/build_release.py 2>/dev/null || true
git commit -m "test: lock in incidents/drafts/ exclusion from validate and build_release"
```

---

## Task 21: Makefile targets

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Inspect current Makefile**

Run: `grep -n '^[a-z].*:' Makefile`
Note existing targets and conventions.

- [ ] **Step 2: Add discover targets**

Append to `Makefile`:

```make
.PHONY: discover discover-fetch discover-stub

discover:          ## Full discovery: fetch candidates + write stubs
	uv run python scripts/fetch_candidates.py
	uv run python scripts/stub_candidates.py

discover-fetch:    ## Stage 1 only — refresh dist/candidates.json
	uv run python scripts/fetch_candidates.py

discover-stub:     ## Stage 2 only — re-run LLM on existing candidates.json
	uv run python scripts/stub_candidates.py
```

- [ ] **Step 3: Smoke test the targets (no network, confirm dispatch)**

Run: `make -n discover`
Expected: prints the two `uv run python` commands without executing them.

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "feat(make): add discover, discover-fetch, discover-stub targets"
```

---

## Task 22: .gitignore update

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append cost log exclusion**

Append to `.gitignore`:

```
# Discovery pipeline cost log (dist/ is already excluded, but pin it):
dist/.discover-cost.log
```

- [ ] **Step 2: Confirm drafts dir is committable (not ignored)**

Run: `git check-ignore -v incidents/drafts/ 2>&1 || echo NOT_IGNORED`
Expected: `NOT_IGNORED` or empty. If the existing `.gitignore` already contains `incidents/.drafts/` (dotted, from v0.2.0), the non-dotted `incidents/drafts/` is unaffected.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore dist/.discover-cost.log"
```

---

## Task 23: Thin enrichment wrapper — scripts/enrich.py

**Files:**
- Create: `scripts/enrich.py`
- Test: `tests/discover/test_enrich_wrapper.py`

Dispatches the existing v0.2.0 enrichment subagent flow (documented in `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md`) on a single incident id. Calls `claude -p` with the subagent prompt template populated with the target id.

- [ ] **Step 1: Write the failing test**

Create `tests/discover/test_enrich_wrapper.py`:

```python
import json
import subprocess
from pathlib import Path
from unittest.mock import patch


def test_enrich_wraps_subagent_prompt_with_given_id(tmp_path, monkeypatch):
    from scripts import enrich

    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        outer = {
            "result": json.dumps({"incident_id": "2024-03-01_db-schenker", "status": "drafted"}),
            "total_cost_usd": 0.05,
            "usage": {"input_tokens": 500, "output_tokens": 200},
        }
        return subprocess.CompletedProcess(args=cmd, returncode=0,
                                           stdout=json.dumps(outer), stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)
    result = enrich.run(incident_id="2024-03-01_db-schenker")

    assert "2024-03-01_db-schenker" in captured["cmd"][2]  # prompt body
    assert result["incident_id"] == "2024-03-01_db-schenker"
    assert result["status"] == "drafted"
    # Enrichment runs sonnet-class model (subagent-driven depth), not haiku.
    assert "--model" in captured["cmd"]
    idx = captured["cmd"].index("--model")
    assert captured["cmd"][idx + 1] == "sonnet"
```

- [ ] **Step 2: Run — confirm failure**

Run: `uv run pytest tests/discover/test_enrich_wrapper.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `scripts/enrich.py`:

```python
"""Thin wrapper around the existing enrichment subagent flow for one incident id.

The enrichment prompt lives at docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md
and uses the sonnet-class model because it performs 20+ web searches
across 5 rounds — this is deliberately not Haiku.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-04-19-enrichment-subagent-prompt.md"
)


def _build_prompt(incident_id: str) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{{INCIDENT_ID}}", incident_id)


def run(*, incident_id: str, timeout_s: int = 1800) -> dict:
    prompt = _build_prompt(incident_id)
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "json"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=True,
    )
    outer = json.loads(proc.stdout)
    raw = outer.get("result", "")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"incident_id": incident_id, "status": "unparseable", "raw": raw}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("incident_id")
    args = ap.parse_args()
    result = run(incident_id=args.incident_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run — confirm pass**

Run: `uv run pytest tests/discover/test_enrich_wrapper.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/enrich.py tests/discover/test_enrich_wrapper.py
git commit -m "feat(discover): scripts/enrich.py thin wrapper around existing v0.2.0 enrichment prompt"
```

---

## Task 24: Full suite green + manual smoke

**Files:** (none — verification only)

- [ ] **Step 1: Run the whole test suite**

Run: `make lint && make validate && make test && make build`
Expected: all four commands exit 0.

- [ ] **Step 2: Frictionless check**

Run: `uv run frictionless validate dist/datapackage.json`
Expected: `valid: true`.

- [ ] **Step 3: Manual smoke (requires live `claude login`)**

Against the real network — maintainer only:

```bash
make discover-fetch
# inspect: dist/candidates.json should contain entries
uv run python -c "import json; print(len(json.load(open('dist/candidates.json'))))"

make discover-stub
# inspect: incidents/drafts/ should contain zero or more stubs
ls incidents/drafts/
```

Expected: ≥1 candidate in `candidates.json`, cost report printed, zero uncaught exceptions. Spot-check 3–5 stubs: does each have `needs_review: true`, a reasonable `description_en`, absolute source URL, and null enums?

- [ ] **Step 4: Update README**

Add a short "Discovering new incidents" section to `README.md` after the existing "Adding or editing an incident" section. Keep to 6–10 lines covering: what `make discover` does, where stubs land, how to promote via enrichment + `promote_drafts.py`.

- [ ] **Step 5: Update CLAUDE.md**

Append under the "Architecture" section a one-paragraph note on the discovery pipeline, mirroring the existing enrichment paragraph: what it does, which scripts are involved, which directory.

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: discover pipeline usage in README and CLAUDE.md"
```

---

## Post-implementation success criteria (from spec)

- `make discover` completes in <5 min on a full backfill run.
- Total LLM spend <$2 for the full backfill.
- ≥80% of produced stubs are genuine railway cyber incidents (maintainer spot-check, random 20-stub sample).
- Zero duplicates vs existing 30 incidents.
- `ruff`, `validate`, `pytest`, `build`, `frictionless` all green.

If the precision target is missed: tune the Pass 1 `CONFIDENCE_FLOOR` upward from 0.6, regenerate the classify-prompt snapshot, re-run on the same `candidates.json` (Stage 1 doesn't need to re-run). That iteration loop is exactly why Stage 1 and Stage 2 are split.

---

## Deferred to a follow-up plan

The spec lists a GDELT / news-search fallback adapter, gated behind a
`--gap YYYY-MM:YYYY-MM` flag, "only used when curated aggregator coverage
looks thin". It is intentionally out of scope for this implementation
plan because:

- The curated aggregators should be measured first; the fallback is
  noisy and token-expensive, and may never be needed.
- Splitting it into its own plan keeps the first rollout small and the
  token bill observable.

Follow-up plan trigger: after one backfill run, if the maintainer
identifies a date window with zero candidates from curated aggregators,
open a new plan to add the GDELT adapter — same shape as the other five
adapters (pure `parse` + `fetch`), plus a `--gap` flag on
`scripts/fetch_candidates.py`.
