from pathlib import Path

from phil_encyclopedia.cli import _payload_from_batch_envelope


def test_payload_from_batch_envelope_skips_empty_model_content(capsys):
    envelope = {
        "custom_id": "sep:cognitive-disability",
        "response": {
            "status_code": 200,
            "body": {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": ""},
                    }
                ],
                "usage": {"completion_tokens": 128000},
            },
        },
    }

    payload = _payload_from_batch_envelope(envelope, Path("results.jsonl"), 36)

    assert payload is None
    output = capsys.readouterr().out
    assert "sep:cognitive-disability" in output
    assert "empty model content" in output
    assert "completion_tokens" in output


def test_payload_from_batch_envelope_skips_non_json_content(capsys):
    envelope = {
        "custom_id": "sep:test",
        "response": {
            "status_code": 200,
            "body": {
                "choices": [
                    {
                        "message": {"content": "Here is the article."},
                    }
                ],
            },
        },
    }

    payload = _payload_from_batch_envelope(envelope, Path("results.jsonl"), 1)

    assert payload is None
    output = capsys.readouterr().out
    assert "sep:test" in output
    assert "model content was not JSON" in output

