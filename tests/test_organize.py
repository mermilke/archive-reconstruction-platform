"""AI-organize tests — fully offline.

The network call is isolated behind an injectable transport, so these tests
cover request building, response parsing, error handling, and turning a
classification into a rendered timeline without ever hitting the API.

Run directly:  python tests/test_organize.py
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc import ai  # noqa: E402
from arc.bridge import ai_email_inputs, assemble_categorized, collect_unique_messages  # noqa: E402
from arc.timeline import render_timeline  # noqa: E402

MAILBOX = os.path.join(ROOT, "examples", "mailbox")


def _emails():
    paths = sorted(glob.glob(os.path.join(MAILBOX, "**", "*.txt"), recursive=True))
    uniques, _total = collect_unique_messages(paths)
    return ai_email_inputs(uniques)


def _fake_classification(emails):
    """A deterministic stand-in for the model: 3 categories, round-robin assigned."""
    cats = [{"id": "eng", "label": "Engineering"},
            {"id": "ops", "label": "Operations"},
            {"id": "biz", "label": "Business"}]
    assigns = []
    for i, e in enumerate(emails):
        assigns.append({
            "id": e["id"],
            "category": cats[i % 3]["id"],
            "importance": i % 4,
            "summary": "Summary for " + e["id"],
        })
    return {"title": "Test Timeline", "categories": cats, "assignments": assigns}


def test_build_request_shape():
    body = ai.build_request([{"id": "e1", "date": "2025-01-01", "from": "A", "subject": "Hi", "snippet": "x"}],
                            model="claude-opus-4-8")
    assert body["model"] == "claude-opus-4-8"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["system"] and body["messages"][0]["role"] == "user"


def test_parse_response_ok_and_errors():
    good = {"content": [{"type": "text", "text": '{"title":"T","categories":[],"assignments":[]}'}]}
    parsed = ai.parse_response(good)
    assert parsed["title"] == "T"

    try:
        ai.parse_response({"stop_reason": "max_tokens", "content": []})
    except ai.AIError:
        pass
    else:
        raise AssertionError("expected AIError on truncated response")

    try:
        ai.parse_response({"content": [{"type": "text", "text": "not json"}]})
    except ai.AIError:
        pass
    else:
        raise AssertionError("expected AIError on invalid JSON")


def test_classify_requires_key():
    try:
        ai.classify_emails([{"id": "e1"}], api_key=None,
                           transport=lambda *a, **k: {})  # transport never reached
    except ai.AIError as e:
        assert "ANTHROPIC_API_KEY" in str(e)
    else:
        raise AssertionError("expected AIError when no API key")


def test_classify_with_injected_transport():
    emails, _items = _emails()
    classification = _fake_classification(emails)
    captured = {}

    def fake_transport(body, api_key, timeout):
        captured["model"] = body["model"]
        return {"content": [{"type": "text", "text": __import__("json").dumps(classification)}]}

    result = ai.classify_emails(emails, api_key="test-key", transport=fake_transport)
    assert captured["model"] == "claude-opus-4-8"
    assert len(result["assignments"]) == len(emails)


def test_assemble_into_timeline():
    emails, items = _emails()
    classification = _fake_classification(emails)
    data = assemble_categorized(MAILBOX, items, classification)

    # 3 categories -> up to 3 groups; every email becomes one event.
    events = [ev for g in data["tabs"][0]["groups"] for ev in g["events"]]
    assert len(events) == len(emails), "every email should become an event"
    assert len(data["categories"]) == 3
    # Every event links back to its source email and carries the AI summary/importance.
    assert all("source" in ev and ev["source"]["href"] for ev in events)
    assert any(ev["summary"].startswith("Summary for ") for ev in events)

    html = render_timeline(data)
    assert "<svg" in html
    for needle in ('src="http', 'href="http', "<link", "@import"):
        assert needle not in html, "unexpected external reference: %s" % needle


def main():
    test_build_request_shape()
    test_parse_response_ok_and_errors()
    test_classify_requires_key()
    test_classify_with_injected_transport()
    test_assemble_into_timeline()
    print("OK - AI organize path verified offline (request/parse/errors/assembly/render).")


if __name__ == "__main__":
    main()
