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

from arc.parse import find_message_files, parse_path  # noqa: E402
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


def main():
    test_threading_headers_are_captured()
    test_forest_shape()
    test_verify_no_loss_with_message_ids()
    test_verify_no_loss_falls_back_without_headers()
    print("OK - thread tree rebuilt; dedup verified to lose 0 messages.")


if __name__ == "__main__":
    main()
