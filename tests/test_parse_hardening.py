"""Parser-hardening + body-normalization tests (roadmap item 2).

Every messy-input behavior is pinned to a synthetic fixture under
``tests/fixtures/messy/`` (Voltera / Drive Assist 3.0 theme). The fixtures cover
quoted replies, ``On <date>, X wrote:`` attribution, ``-----Original Message-----``
forwards, signatures, timezone-shifted duplicates, folded headers, a
missing-blank malformed block, a no-``From`` block, and an empty file.

The core claim this protects: a body's *identity* should depend only on the
sender and the message's own content — not on whether an export pasted a
quote-tail, a signature, or a different timezone onto it.

Run directly:  python tests/test_parse_hardening.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.dedup import analyze, content_keys, message_key  # noqa: E402
from arc.normalize import (  # noqa: E402
    clean_for_fingerprint,
    strip_quoted,
    strip_signature,
)
from arc.parse import Message, parse_path, parse_thread  # noqa: E402

MESSY = os.path.join(ROOT, "tests", "fixtures", "messy")


def fixture(name):
    return os.path.join(MESSY, name)


# --- normalization is conservative: clean bodies pass through untouched -------

def test_clean_body_is_a_noop():
    clean = "Runbook attached. The auto-halt trips beyond the beta baseline. Raj"
    assert clean_for_fingerprint(clean) == clean
    assert strip_quoted(clean) == clean
    assert strip_signature(clean) == clean


# --- quoted replies / attribution lines --------------------------------------

def test_quoted_reply_is_stripped_from_fingerprint():
    msgs = parse_path(fixture("quoted_reply.txt"))
    assert len(msgs) == 1, "gmail-style quote should not start a new message block"
    # The full body is preserved for display...
    assert "wrote:" in msgs[0].body.lower()
    # ...but the fingerprint sees only this message's own content.
    cleaned = clean_for_fingerprint(msgs[0].body)
    assert "wrote:" not in cleaned.lower()
    assert ">" not in cleaned
    assert "perception rc3" not in cleaned.lower()      # quoted prior message gone
    assert "leadership review" in cleaned.lower()        # own content kept


def test_quoted_reply_matches_standalone_copy():
    """Same reply, pasted standalone vs with a quote-tail = one identity."""
    quoted = parse_path(fixture("quoted_reply.txt"))[0]
    standalone = Message(
        sender="Lena Ortiz <lena.ortiz@voltera.example>",
        body=(
            "Great. For the leadership review I will need the rollout runbook "
            "and the auto-halt criteria attached. Can you send those over? Lena"
        ),
    )
    assert message_key(quoted) == message_key(standalone)


# --- forwarded / original-message blocks -------------------------------------

def test_original_message_block_is_stripped():
    msgs = parse_path(fixture("outlook_forward.txt"))
    assert len(msgs) == 1, "an -----Original Message----- run should not split the file"
    cleaned = clean_for_fingerprint(msgs[0].body)
    assert "original message" not in cleaned.lower()
    assert "safety case is approved" not in cleaned.lower()  # forwarded content gone
    assert "forwarding the signed safety case" in cleaned.lower()


# --- signatures ---------------------------------------------------------------

def test_signature_is_stripped_but_attachment_survives():
    msgs = parse_path(fixture("signature.txt"))
    assert len(msgs) == 1
    cleaned = clean_for_fingerprint(msgs[0].body)
    assert "staff engineer" not in cleaned.lower()  # signature gone
    assert "auto-halt" in cleaned.lower()           # body kept
    # The attachment is a first-class content key regardless of the signature.
    assert ("att", "", "rollout_runbook.pdf") in content_keys(msgs)


# --- timezone-shifted duplicates collapse to one -----------------------------

def test_timezone_duplicates_collapse():
    ku = content_keys(parse_path(fixture("tz_dupe_utc.txt")))
    kp = content_keys(parse_path(fixture("tz_dupe_pacific.txt")))
    assert ku == kp, "same message, different timezone, must share one identity"

    result = analyze([("tz_dupe_utc.txt", ku), ("tz_dupe_pacific.txt", kp)])
    assert set(result.keep) | set(result.delete) == {
        "tz_dupe_utc.txt",
        "tz_dupe_pacific.txt",
    }
    assert len(result.keep) == 1, "the pair must collapse to a single keeper"
    assert result.keep == ["tz_dupe_pacific.txt"]  # lexicographically smaller name wins


# --- malformed / folded / empty blocks ---------------------------------------

def test_missing_blank_line_still_yields_a_body():
    msgs = parse_path(fixture("malformed_no_blank.txt"))
    assert len(msgs) == 1
    assert "lena.ortiz@voltera.example" in msgs[0].sender.lower()
    assert "1% canary" in msgs[0].body
    # The trailing header before the body must not be swallowed into the body.
    assert not msgs[0].body.lower().startswith("subject:")


def test_folded_header_is_stitched():
    msgs = parse_path(fixture("folded_header.txt"))
    assert len(msgs) == 1
    assert msgs[0].subject == "Drive Assist 3.0 - canary go/no-go"
    assert "raj.patel@voltera.example" in msgs[0].recipient.lower()
    assert "1% canary" in msgs[0].body


def test_no_from_block_anchors_nothing():
    assert parse_path(fixture("headers_only_no_from.txt")) == []


def test_empty_file_and_whitespace():
    assert parse_path(fixture("empty.txt")) == []
    assert parse_thread("") == []
    assert parse_thread("   \n\t\n   ") == []


# --- identical-content tie-break is deterministic -----------------------------

def test_identical_content_tie_break_keeps_one():
    keys = {("msg", "raj.patel@voltera.example", "go for canary")}
    # Order of input must not matter: the lexicographically smaller name is kept.
    result = analyze([("b_copy.txt", set(keys)), ("a_copy.txt", set(keys))])
    assert result.keep == ["a_copy.txt"]
    assert result.delete == ["b_copy.txt"]


def main():
    test_clean_body_is_a_noop()
    test_quoted_reply_is_stripped_from_fingerprint()
    test_quoted_reply_matches_standalone_copy()
    test_original_message_block_is_stripped()
    test_signature_is_stripped_but_attachment_survives()
    test_timezone_duplicates_collapse()
    test_missing_blank_line_still_yields_a_body()
    test_folded_header_is_stitched()
    test_no_from_block_anchors_nothing()
    test_empty_file_and_whitespace()
    test_identical_content_tie_break_keeps_one()
    print("OK - parser hardening: quotes/forwards/signatures/timezones/malformed all handled.")


if __name__ == "__main__":
    main()
