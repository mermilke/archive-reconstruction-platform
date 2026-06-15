"""SQLite store tests (roadmap item 4).

The store accumulates unique messages across runs. Identity is the same content
key dedup uses, so dedup computed *from the store* must match dedup over the
original files; re-ingesting a folder must not double-count; and a timeline can
be rendered from everything stored.

Uses an in-memory database (one connection reused across calls) plus a temp
folder of distinct synthetic messages for the accumulation check.

Run directly:  python tests/test_store.py
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc import store  # noqa: E402
from arc.dedup import dedup_directory  # noqa: E402
from arc.bridge import timeline_data_from_messages  # noqa: E402
from arc.timeline import render_timeline  # noqa: E402

EXAMPLES = os.path.join(ROOT, "examples", "threads")

# Two messages on a topic that appears nowhere else in the sample data, so the
# accumulation test is independent of the (deliberately consistent) Voltera text.
TELEMETRY_A = """From: Priya Nair <priya.nair@voltera.example>
Sent: 2025-10-02 09:15
To: Sam Cole <sam.cole@voltera.example>
Subject: Telemetry pipeline backfill

Sam, the telemetry backfill for the beta fleet completed overnight. Dashboards are green. Priya
"""

TELEMETRY_B = """From: Sam Cole <sam.cole@voltera.example>
Sent: 2025-10-02 13:40
To: Priya Nair <priya.nair@voltera.example>
Subject: RE: Telemetry pipeline backfill

Thanks Priya. I will flag the disengagement metric to the rollout review. Sam
"""


def _fresh():
    return store.connect(":memory:")


def test_add_examples_counts():
    conn = _fresh()
    res = store.add_directory(conn, EXAMPLES)
    assert res.files_added == 6
    st = store.stats(conn)
    assert st.files == 6
    assert st.messages == 5, "examples/threads has 5 unique messages, got %d" % st.messages
    # Both branch attachments are recorded.
    assert st.attachments == 2, st.attachments
    conn.close()


def test_store_dedup_matches_file_dedup():
    conn = _fresh()
    store.add_directory(conn, EXAMPLES)
    store_result = store.dedup(conn)
    file_result = dedup_directory(EXAMPLES)
    assert set(store_result.keep) == set(file_result.keep)
    assert set(store_result.delete) == set(file_result.delete)
    assert set(store_result.keep) == {
        "thread_forward_attachment.txt",
        "thread_main_full.txt",
    }
    conn.close()


def test_reingest_is_idempotent():
    conn = _fresh()
    store.add_directory(conn, EXAMPLES)
    before = store.stats(conn)
    res2 = store.add_directory(conn, EXAMPLES)
    after = store.stats(conn)
    assert res2.files_added == 0
    assert res2.files_refreshed == 6
    assert res2.messages_added == 0, "re-ingest must not add new messages"
    assert (after.files, after.messages) == (before.files, before.messages)
    conn.close()


def test_accumulates_across_folders():
    tmp = tempfile.mkdtemp(prefix="ett_store_")
    try:
        with open(os.path.join(tmp, "telemetry_a.txt"), "w", encoding="utf-8") as fh:
            fh.write(TELEMETRY_A)
        with open(os.path.join(tmp, "telemetry_b.txt"), "w", encoding="utf-8") as fh:
            fh.write(TELEMETRY_B)

        conn = _fresh()
        store.add_directory(conn, EXAMPLES)
        store.add_directory(conn, tmp)
        st = store.stats(conn)
        assert st.files == 8, st.files          # 6 + 2
        assert st.messages == 7, st.messages    # 5 + 2 distinct

        # Both telemetry files are unique branches (neither a subset of anything).
        result = store.dedup(conn)
        assert "telemetry_a.txt" in result.keep
        assert "telemetry_b.txt" in result.keep
        conn.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_timeline_from_store_renders():
    conn = _fresh()
    store.add_directory(conn, EXAMPLES)
    items = store.load_messages(conn)
    assert len(items) == 5
    data = timeline_data_from_messages(items, title="From store")
    events = [ev for tab in data["tabs"] for g in tab["groups"] for ev in g["events"]]
    assert len(events) == 5
    html = render_timeline(data)
    assert "<svg" in html
    for needle in ('src="http', 'href="http', "<link", "@import"):
        assert needle not in html
    conn.close()


def main():
    test_add_examples_counts()
    test_store_dedup_matches_file_dedup()
    test_reingest_is_idempotent()
    test_accumulates_across_folders()
    test_timeline_from_store_renders()
    print("OK - sqlite store accumulates, dedups identically, and renders a timeline.")


if __name__ == "__main__":
    main()
