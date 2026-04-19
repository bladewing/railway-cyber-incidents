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


def test_matches_rail_accepts_english_plurals():
    kws = {"railway", "train", "metro"}
    assert matches_rail("Swiss Federal Railways confirm hack", kws)
    assert matches_rail("Two trains were affected", kws)
    assert matches_rail("multiple metros down", kws)


def test_matches_rail_plural_does_not_match_longer_word():
    # ``training`` must not match ``train`` even with the optional
    # plural — the ``s?`` still requires a trailing word boundary.
    kws = {"train"}
    assert not matches_rail("Vocational Education and Training Institute", kws)


def test_matches_rail_german_compounds_from_vocab():
    # Load the real vocabulary so this doubles as a regression test
    # for the compound entries we added.
    assert matches_rail("Rostocker Straßenbahn AG")
    assert matches_rail("S-Bahn Berlin outage")
    assert matches_rail("U-Bahn Hamburg service restored")
    assert matches_rail("Deutsche Bahn Eisenbahn incident")
    # ``Autobahn`` is a road; the compound list must deliberately
    # exclude it so we never flag highway-authority breaches as rail.
    assert not matches_rail("Autobahn GmbH des Bundes compromised")
