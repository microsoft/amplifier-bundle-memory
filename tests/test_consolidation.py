import pytest

from amplifier_memory.consolidation import build_request, relevant, verified_candidates


def test_workspace_policy_is_explicit_and_personal_default_unchanged():
    turns = ["We settled on PostgreSQL because the event store needs transactional writes."]
    assert "personal working preferences" in build_request(turns)
    assert "settled project decisions" in build_request(turns, policy="workspace")
    assert "untrusted reference data" in build_request(turns)
    with pytest.raises(ValueError):
        build_request(turns, policy="all")


def test_verified_candidates_require_supported_human_quote():
    turns = ["For status updates, a short paragraph is easier for me to scan than bullets."]
    good = '[{"text":"Prefer paragraph status updates.","quote":"a short paragraph is easier for me to scan than bullets."}]'
    assert verified_candidates(good, turns)[0]["wording"] == "model-derived"
    assert verified_candidates(good, ["The build passed."]) == []
    assert verified_candidates(good, ["<system-reminder>" + turns[0] + "</system-reminder>"]) == []


def test_input_and_output_bounds_do_not_truncate_quotes():
    with pytest.raises(ValueError):
        build_request(["A" * 16000])
    with pytest.raises(ValueError):
        verified_candidates('[{"text":"x","quote":"an exact human quotation"},' * 8 + '{"text":"x","quote":"an exact human quotation"}]', [])


def test_supersession_requires_a_known_identity_and_attributable_quote():
    turns = ['I changed my mind: use PostgreSQL for the event store.']
    known = [{'id':'old', 'text':'Use SQLite for the event store.'}]
    reply = '[{"text":"Use PostgreSQL for the event store.","quote":"use PostgreSQL for the event store.","supersedes":["old"]}]'
    assert verified_candidates(reply, turns, known=known)[0]['supersedes']==['old']
    assert verified_candidates(reply, turns)==[]
    assert 'old' in build_request(turns, policy='workspace', known=known)


def test_relevance_returns_only_matches_and_explains_terms():
    notes = [{'id':'one','text':'Use paragraphs for status updates.'},
             {'id':'two','text':'The event store uses PostgreSQL.'}]
    assert [row['id'] for row in relevant(notes, 'Draft a status update.')]==['one']
    assert not relevant(notes, 'What is seventeen times twenty three?')
