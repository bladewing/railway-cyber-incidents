"""Rail-adjacency keyword loader and whole-word matcher.

The matcher allows an optional trailing ``s`` so that English plurals
(``railways``, ``trains``, ``metros``) match their singular keywords
without having to double-list every term. German compounds that we
cannot catch with whole-word matching (``Straßenbahn``, ``S-Bahn``)
are listed explicitly in ``vocabularies/rail_keywords.yaml``.
"""

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
        if re.search(rf"\b{re.escape(k.lower())}s?\b", hay):
            return True
    return False
