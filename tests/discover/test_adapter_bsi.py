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
