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
