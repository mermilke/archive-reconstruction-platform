"""Real-format ingestion tests: .eml and .mbox parse into the Message model and
flow through dedup keys and the timeline bridge.

Requires the fixtures in examples/raw_email/ (run scripts/generate_sample_raw_email.py).

Run directly:  python tests/test_email_in.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.dedup import content_keys, message_key  # noqa: E402
from arc.email_in import parse_eml, parse_mbox  # noqa: E402
from arc.parse import find_message_files, parse_path  # noqa: E402
from arc.bridge import build_timeline_data  # noqa: E402
from arc.timeline import render_timeline  # noqa: E402

RAW = os.path.join(ROOT, "examples", "raw_email")


def _eml(name):
    return parse_eml(os.path.join(RAW, name))[0]


def test_eml_basic_fields():
    m = _eml("01_canary_go_no_go.eml")
    assert "lena.ortiz@voltera.example" in m.sender.lower()
    assert "raj.patel@voltera.example" in m.recipient.lower()
    assert m.subject == "Drive Assist 3.0 - canary go/no-go"
    assert m.timestamp.startswith("2025-11-24"), m.timestamp
    assert "canary" in m.body.lower()


def test_eml_encoded_subject_and_attachment():
    m = _eml("02_runbook_attached.eml")
    # RFC 2047-encoded subject must come back as decoded Unicode.
    assert "✅" in m.subject, repr(m.subject)
    assert "canary" in m.subject.lower()
    assert m.attachments == ["rollout_runbook.pdf"], m.attachments


def test_eml_html_body_is_flattened():
    m = _eml("03_perception_signoff.eml")
    assert "<" not in m.body and ">" not in m.body, "HTML tags should be stripped"
    assert "rc3" in m.body and "signed off" in m.body.lower()


def test_mbox_yields_all_messages():
    msgs = parse_mbox(os.path.join(RAW, "team.mbox"))
    assert len(msgs) == 3, "expected 3 messages in the mbox, got %d" % len(msgs)
    subjects = {m.subject for m in msgs}
    assert "Safety case approved" in subjects
    # Attachment inside an mbox message is read too.
    safety = next(m for m in msgs if m.subject == "Safety case approved")
    assert safety.attachments == ["safety_case_final.pdf"], safety.attachments


def test_content_keys_work_on_real_email():
    # The same content-key model applies — sender + body fingerprint, attachments.
    m = _eml("02_runbook_attached.eml")
    keys = content_keys([m])
    assert message_key(m) in keys
    assert ("att", "", "rollout_runbook.pdf") in keys


def test_finder_picks_up_eml_and_mbox():
    files = find_message_files(RAW)
    exts = {os.path.splitext(f)[1].lower() for f in files}
    assert ".eml" in exts and ".mbox" in exts, exts
    # parse_path dispatches correctly per extension.
    total = sum(len(parse_path(f)) for f in files)
    assert total == 6, "3 eml + 3 mbox messages = 6, got %d" % total


def test_timeline_from_real_email_renders():
    data = build_timeline_data(RAW)
    events = [ev for tab in data["tabs"] for g in tab["groups"] for ev in g["events"]]
    assert len(events) == 6, "expected 6 unique messages, got %d" % len(events)
    html = render_timeline(data)
    assert "<svg" in html
    for needle in ('src="http', 'href="http', "<link", "@import"):
        assert needle not in html


def main():
    test_eml_basic_fields()
    test_eml_encoded_subject_and_attachment()
    test_eml_html_body_is_flattened()
    test_mbox_yields_all_messages()
    test_content_keys_work_on_real_email()
    test_finder_picks_up_eml_and_mbox()
    test_timeline_from_real_email_renders()
    print("OK - .eml and .mbox ingest into the Message model and render a timeline.")


if __name__ == "__main__":
    main()
