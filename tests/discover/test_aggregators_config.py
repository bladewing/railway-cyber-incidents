from scripts.discover.aggregators_config import load_aggregators


def test_load_returns_at_least_five_enabled_sources():
    aggs = load_aggregators()
    enabled_ids = {a.id for a in aggs if a.enabled}
    assert {"konbriefing", "eurepoc", "enisa_transport", "ransomware_live", "bsi_lagebericht"} <= enabled_ids


def test_each_aggregator_has_kind_and_url_or_pdfs():
    for a in load_aggregators():
        assert a.kind in {"html", "json", "pdf", "csv"}
        assert a.id
        if a.kind == "pdf":
            # PDFs list may be empty until maintainer supplies stable URLs
            assert isinstance(a.pdfs, tuple)
        else:
            assert a.url  # non-pdf aggregators must have a URL
