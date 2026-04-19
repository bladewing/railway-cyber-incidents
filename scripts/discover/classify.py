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
