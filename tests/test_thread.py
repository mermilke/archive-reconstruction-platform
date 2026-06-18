"""Thread-tree reconstruction + dedup verification (roadmap item 3).

`tests/fixtures/threaded/` holds one Voltera conversation, exported three ways,
with RFC 5322 threading headers (Message-ID / In-Reply-To / References):

* thread_full.txt   -- main branch, ending in a reply that attaches the runbook
* thread_branch.txt -- a forward branch carrying a unique attachment
* thread_subset.txt -- just the opener + first reply (a strict subset)

The genuine reply tree is::

    * open
      - eng
        - ask            (linked via References only -- no In-Reply-To)
          - fwd
          - runbook

Dedup (content only) keeps the two branches and drops the subset; this test
proves -- via the reconstructed tree -- that no message is lost in doing so.

Run directly:  python tests/test_thread.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import shutil  # noqa: E402
import tempfile  # noqa: E402

from arc.parse import find_message_files, parse_path, parse_thread  # noqa: E402
from arc.thread import build_forest, verify_no_loss, walk  # noqa: E402

THREADED = os.path.join(ROOT, "tests", "fixtures", "threaded")
EXAMPLES = os.path.join(ROOT, "examples", "threads")


def _mid(token):
    return ("mid", token)


def _all_messages(directory):
    msgs = []
    for p in find_message_files(directory):
        msgs.extend(parse_path(p))
    return msgs


# --- headers are captured off both the .txt format ---------------------------

def test_threading_headers_are_captured():
    full = parse_path(os.path.join(THREADED, "thread_full.txt"))
    top = full[0]
    assert top.message_id == "<c1-runbook@voltera.example>"
    assert top.in_reply_to == "<c1-ask@voltera.example>"
    assert top.references == [
        "<c1-open@voltera.example>",
        "<c1-eng@voltera.example>",
        "<c1-ask@voltera.example>",
    ]
    # The "ask" message references its ancestry but carries no In-Reply-To.
    ask_msg = full[1]
    assert ask_msg.in_reply_to == ""
    assert len(ask_msg.references) == 2


# --- the reply forest is rebuilt correctly -----------------------------------

def test_forest_shape():
    forest = build_forest(_all_messages(THREADED))
    assert len(forest) == 1, "the whole conversation should rebuild as one tree"

    root = forest[0]
    assert root.identity == _mid("c1-open@voltera.example")
    assert root.depth == 0

    nodes = {n.identity: n for n in walk(forest)}
    eng = nodes[_mid("c1-eng@voltera.example")]
    ask = nodes[_mid("c1-ask@voltera.example")]
    assert eng.depth == 1
    assert ask.depth == 2

    # "ask" was linked under "eng" using References alone (no In-Reply-To).
    assert ask.identity in {c.identity for c in eng.children}

    # The thread branches at "ask": two replies, both one level deeper.
    assert {c.identity for c in ask.children} == {
        _mid("c1-fwd@voltera.example"),
        _mid("c1-runbook@voltera.example"),
    }
    for child in ask.children:
        assert child.depth == 3


# --- dedup is verified against the reconstructed conversation ----------------

def test_verify_no_loss_with_message_ids():
    report = verify_no_loss(THREADED)
    assert report.files_total == 3
    assert report.branches_kept == 2
    assert report.unique_messages == 5
    assert report.lost == []
    assert report.ok
    assert report.benchmark_line() == (
        "Collapsed 3 files -> 2 branches; 5 unique messages, 0 lost."
    )


def test_verify_no_loss_falls_back_without_headers():
    """The original examples carry no threading headers; identity falls back to
    content, and dedup still provably loses nothing."""
    report = verify_no_loss(EXAMPLES)
    assert report.files_total == 6
    assert report.branches_kept == 2
    assert report.unique_messages == 5
    assert report.ok

    # With no In-Reply-To/References, every unique message is its own root.
    forest = build_forest(_all_messages(EXAMPLES))
    assert len(forest) == 5
    assert all(node.depth == 0 for node in forest)


# The opener, exported twice: once inside a 2-message thread that carries
# Message-IDs, and once on its own with NO Message-ID. The id-less copy is a
# strict content subset, so dedup deletes it. Its content lives in the kept file,
# so it must be reported as a *collapsed cross-format duplicate*, not a loss.
_WITH_ID = """\
From: Raj Patel <raj@voltera.example>
Sent: 2025-03-02 10:00
To: Lena Ortiz <lena@voltera.example>
Subject: RE: Canary plan
Message-ID: <reply@voltera.example>
In-Reply-To: <open@voltera.example>

Sounds good, shipping the canary tonight.

From: Lena Ortiz <lena@voltera.example>
Sent: 2025-03-01 09:00
To: Raj Patel <raj@voltera.example>
Subject: Canary plan
Message-ID: <open@voltera.example>

Here is the canary rollout plan for review.
"""

_NO_ID = """\
From: Lena Ortiz <lena@voltera.example>
Sent: 2025-03-01 09:00
To: Raj Patel <raj@voltera.example>
Subject: Canary plan

Here is the canary rollout plan for review.
"""


def test_mixed_id_corpus_collapses_without_reporting_loss():
    tmp = tempfile.mkdtemp(prefix="arc_mixed_")
    try:
        with open(os.path.join(tmp, "with_id.txt"), "w", encoding="utf-8") as fh:
            fh.write(_WITH_ID)
        with open(os.path.join(tmp, "no_id.txt"), "w", encoding="utf-8") as fh:
            fh.write(_NO_ID)

        report = verify_no_loss(tmp)
        assert report.files_total == 2
        assert report.branches_kept == 1, "the id-less subset should be deleted"
        # The opener appears under a Message-ID (kept) and id-less (deleted); its
        # content is preserved, so it's collapsed, not lost.
        assert report.lost == [], f"no real content loss, got {report.lost}"
        assert report.collapsed == 1, f"expected 1 cross-format duplicate, got {report.collapsed}"
        assert report.ok
        assert "0 lost" in report.benchmark_line()
        assert "1 cross-format duplicate collapsed" in report.benchmark_line()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# Two replies to one root whose timestamps sort the OTHER way as strings than as
# dates: "9:00" > "10:00" lexicographically, but 09:00 < 10:00 chronologically.
_SIBLING_ORDER = """From: Ana <ana@voltera.example>
Sent: 2025-03-08 08:00
Subject: Canary plan
Message-ID: <root@voltera.example>

Root message.

From: Bo <bo@voltera.example>
Sent: 2025-03-09 9:00
Subject: RE: Canary plan
Message-ID: <r1@voltera.example>
In-Reply-To: <root@voltera.example>

Earlier reply at nine.

From: Cy <cy@voltera.example>
Sent: 2025-03-09 10:00
Subject: RE: Canary plan
Message-ID: <r2@voltera.example>
In-Reply-To: <root@voltera.example>

Later reply at ten.
"""


def test_siblings_order_chronologically_not_lexicographically():
    forest = build_forest(parse_thread(_SIBLING_ORDER))
    assert len(forest) == 1, "one root conversation"
    order = [n.message.sender.split()[0] for n in walk(forest)]
    # Root, then the 09:00 reply, then the 10:00 reply — by real time, even though
    # "10:00" sorts before "9:00" as a string.
    assert order == ["Ana", "Bo", "Cy"], f"siblings out of chronological order: {order}"


def main():
    test_threading_headers_are_captured()
    test_forest_shape()
    test_verify_no_loss_with_message_ids()
    test_verify_no_loss_falls_back_without_headers()
    test_mixed_id_corpus_collapses_without_reporting_loss()
    test_siblings_order_chronologically_not_lexicographically()
    print("OK - thread tree rebuilt; dedup verified to lose 0 messages.")


if __name__ == "__main__":
    main()
