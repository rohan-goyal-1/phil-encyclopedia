from phil_encyclopedia.processing.qa import validate_generated_payload


def valid_payload():
    level = {
        "summary": "This entry explains a philosophical topic in clear words for students. It describes the main question, why philosophers care about it, and how different answers can be compared without pretending one side is easy.",
        "key_ideas": ["Philosophers ask careful questions.", "Different answers need reasons."],
        "important_terms": [
            {"term": "argument", "definition": "A set of reasons offered for a conclusion."},
            {"term": "concept", "definition": "An idea used to understand something."},
        ],
        "example": "A student might ask whether a promise still matters when keeping it becomes difficult.",
        "why_it_matters": "The topic helps readers notice assumptions and explain their reasons more clearly.",
        "questions_to_think_about": ["What reason is strongest?", "What would change your mind?"],
        "reading_time_minutes": 3,
    }
    return {
        "sep_slug": "test",
        "sep_url": "https://plato.stanford.edu/entries/test/",
        "title": "Test",
        "source_title": "Test",
        "attribution": "Based on the Stanford Encyclopedia of Philosophy entry: Test",
        "read_more_url": "https://plato.stanford.edu/entries/test/",
        "elementary": level,
        "middle": level,
        "high_school": level,
        "sensitive_topic": False,
        "sensitive_topic_reasons": [],
    }


def test_validator_accepts_valid_payload():
    result = validate_generated_payload(valid_payload())
    assert result.passed is True
    assert result.status == "passed"


def test_validator_rejects_missing_field():
    payload = valid_payload()
    del payload["elementary"]["summary"]
    result = validate_generated_payload(payload)
    assert result.passed is False
    assert result.status == "failed"


def test_validator_rejects_copied_passage():
    payload = valid_payload()
    copied = "one two three four five six seven eight nine ten eleven twelve"
    payload["middle"]["summary"] = copied + " with a little extra explanation for length and clarity."
    source = f"Before {copied} after"
    result = validate_generated_payload(payload, source_text=source)
    assert result.passed is False
    assert result.status == "failed"


def test_validator_routes_sensitive_topics_to_manual_review():
    payload = valid_payload()
    payload["high_school"]["summary"] += " It also discusses death in a careful philosophical way."
    result = validate_generated_payload(payload)
    assert result.passed is False
    assert result.status == "needs_manual_review"
