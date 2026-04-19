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
