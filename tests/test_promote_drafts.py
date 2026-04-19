from pathlib import Path
import yaml
import pytest

from scripts.promote_drafts import promote, PromotionError


def _make_draft(repo: Path, incident_id: str, doc: dict) -> Path:
    drafts = repo / "incidents" / ".drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    path = drafts / f"{incident_id}.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def _make_original(repo: Path, incident_id: str, doc: dict) -> Path:
    path = repo / "incidents" / f"{incident_id}.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def test_only_promotes_single_incident(tmp_repo, minimal_incident):
    incident_id = minimal_incident["id"]
    _make_original(tmp_repo, incident_id, {"id": incident_id, "stub": True})
    _make_draft(tmp_repo, incident_id, minimal_incident)

    promoted = promote(tmp_repo, only=[incident_id])

    assert promoted == [incident_id]
    final_path = tmp_repo / "incidents" / f"{incident_id}.yaml"
    assert yaml.safe_load(final_path.read_text()) == minimal_incident
    assert not (tmp_repo / "incidents" / ".drafts" / f"{incident_id}.yaml").exists()


def test_refuses_to_promote_when_draft_uses_unknown_vocab(tmp_repo, minimal_incident):
    incident_id = minimal_incident["id"]
    draft = dict(minimal_incident)
    # affected_systems references a value not in vocabularies/affected_systems.yaml
    draft["affected_systems"] = ["not_a_real_system"]
    _make_draft(tmp_repo, incident_id, draft)

    with pytest.raises(PromotionError, match="not_a_real_system"):
        promote(tmp_repo, only=[incident_id])

    # Draft must still be in place — nothing moved.
    assert (tmp_repo / "incidents" / ".drafts" / f"{incident_id}.yaml").exists()


def test_refuses_to_promote_when_source_type_unknown(tmp_repo, minimal_incident):
    """sources[].type is vocab-controlled — must be checked by the pre-flight."""
    incident_id = minimal_incident["id"]
    draft = dict(minimal_incident)
    draft["sources"] = [
        {"url": "https://example.org/a", "type": "twitter_thread"},  # not in source_types.yaml
    ]
    _make_draft(tmp_repo, incident_id, draft)

    with pytest.raises(PromotionError, match="twitter_thread"):
        promote(tmp_repo, only=[incident_id])

    assert (tmp_repo / "incidents" / ".drafts" / f"{incident_id}.yaml").exists()


def test_batch_promotion_is_atomic_on_vocab_failure(tmp_repo, minimal_incident):
    """A bad apple in the batch must NOT leave earlier candidates partially moved."""
    good_id = minimal_incident["id"]
    _make_draft(tmp_repo, good_id, minimal_incident)

    bad_id = "2020-02-02_broken"
    bad_draft = dict(minimal_incident, id=bad_id, affected_systems=["not_a_real_system"])
    _make_draft(tmp_repo, bad_id, bad_draft)

    with pytest.raises(PromotionError, match="not_a_real_system"):
        promote(tmp_repo, only=[good_id, bad_id])

    # Neither draft may have moved — pre-flight must reject the whole batch.
    assert (tmp_repo / "incidents" / ".drafts" / f"{good_id}.yaml").exists()
    assert (tmp_repo / "incidents" / ".drafts" / f"{bad_id}.yaml").exists()
    assert not (tmp_repo / "incidents" / f"{good_id}.yaml").exists()
    assert not (tmp_repo / "incidents" / f"{bad_id}.yaml").exists()
