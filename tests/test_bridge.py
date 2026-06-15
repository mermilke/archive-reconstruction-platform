"""Bridge test: a folder of threads becomes deduplicated timeline data.

The six example files contain only five distinct messages (R1, R2, A3, A4 on the
"slot" thread and B3 on the "hospitality rider" thread). The bridge should
collapse every duplicate and produce one event per unique message, grouped into
the two subject threads and colored by the two senders.

Run directly:  python tests/test_bridge.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.bridge import base_subject, build_timeline_data  # noqa: E402
from arc.timeline import render_timeline  # noqa: E402

THREADS = os.path.join(ROOT, "examples", "threads")


def _all_events(data):
    return [ev for tab in data["tabs"] for g in tab["groups"] for ev in g["events"]]


def test_dedup_to_unique_messages():
    data = build_timeline_data(THREADS)
    events = _all_events(data)
    assert len(events) == 5, "expected 5 unique messages, got %d" % len(events)

    groups = data["tabs"][0]["groups"]
    assert len(groups) == 2, "expected 2 subject threads, got %d" % len(groups)

    # Two conversation threads -> two (topic) categories.
    assert len(data["categories"]) == 2, "expected 2 topics, got %d" % len(data["categories"])

    # The duplicate count is reported (6 files, 5 unique -> several collapsed).
    assert "after dedup" in data["subtitle"]


def test_attachments_and_openers_are_highlighted():
    data = build_timeline_data(THREADS)
    events = _all_events(data)

    with_attachments = [e for e in events if e.get("attachments")]
    names = sorted(a for e in with_attachments for a in e["attachments"])
    assert names == ["rollout_runbook.pdf", "safety_case_final.pdf"], names

    # Attachment-bearing messages are flagged as notable.
    for e in with_attachments:
        assert e["importance"] == 2, "attachment message should be importance 2"


def test_base_subject_strips_prefixes():
    assert base_subject("RE: FW: Hello") == "Hello"
    assert base_subject("Fwd: Re: Trip") == "Trip"
    assert base_subject("No prefix") == "No prefix"


def test_renders_to_self_contained_html():
    data = build_timeline_data(THREADS)
    html = render_timeline(data)
    assert "<svg" in html and "tab-pane" in html
    # No external assets in the generated page.
    for needle in ('src="http', 'href="http', "<link", "@import"):
        assert needle not in html, "unexpected external reference: %s" % needle


def main():
    test_dedup_to_unique_messages()
    test_attachments_and_openers_are_highlighted()
    test_base_subject_strips_prefixes()
    test_renders_to_self_contained_html()
    print("OK - 6 thread files collapsed to 5 unique messages across 2 conversations.")


if __name__ == "__main__":
    main()
