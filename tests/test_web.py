"""Local web UI tests (roadmap item 5).

The web UI must not invent any new dedup/timeline behavior — it writes dropped
files into a temp working dir and reuses the same folder pipeline as the CLI.
So the contract to pin is:

* uploading the six synthetic example threads yields the SAME keep/delete call
  as ``dedup_directory`` (keep 2 branches, flag 4 subsets);
* a timeline built from the selected keepers renders real events;
* unsupported file types are skipped, not parsed;
* the HTTP surface (upload -> state -> build -> /timeline) works end to end and
  serves only local, self-contained HTML.

Stdlib only (``urllib`` drives the live HTTP round-trip). Run directly:

    python tests/test_web.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc import web  # noqa: E402
from arc.dedup import dedup_directory  # noqa: E402

EXAMPLES = os.path.join(ROOT, "examples", "threads")


def _example_uploads():
    """Read the synthetic example threads as browser-style upload records."""
    uploads = []
    for name in sorted(os.listdir(EXAMPLES)):
        path = os.path.join(EXAMPLES, name)
        if os.path.isfile(path) and name.lower().endswith(".txt"):
            with open(path, "r", encoding="utf-8") as fh:
                uploads.append({"name": name, "content": fh.read()})
    return uploads


def test_session_matches_dedup_directory():
    """Uploading the examples reproduces the CLI's branch-aware verdict exactly."""
    sess = web.Session()
    uploads = _example_uploads()
    saved, skipped = sess.save_uploads(uploads)
    assert saved == len(uploads), "all .txt examples should save"
    assert skipped == [], "no example should be skipped"

    state = sess.state()
    summary = state["summary"]

    # Ground truth: the same analysis the `dedup` command runs.
    expected = dedup_directory(EXAMPLES)
    assert summary["files"] == len(expected.reports)
    assert summary["kept"] == len(expected.keep) == 2, "two branches kept"
    assert summary["redundant"] == len(expected.delete) == 4, "four subsets flagged"

    web_keep = sorted(f["name"] for f in state["files"] if not f["redundant"])
    web_del = sorted(f["name"] for f in state["files"] if f["redundant"])
    assert web_keep == sorted(expected.keep)
    assert web_del == sorted(expected.delete)

    # Each redundant file names a keeper that covers it.
    for f in state["files"]:
        if f["redundant"]:
            assert f["coveredBy"], "a redundant file must report what supersedes it"

    sess.reset()
    assert sess.state()["files"] == [], "reset clears the working set"
    print("OK - upload reproduces dedup_directory: kept %d, flagged %d."
          % (summary["kept"], summary["redundant"]))


def test_skips_unsupported_and_sanitizes_names():
    sess = web.Session()
    saved, skipped = sess.save_uploads([
        {"name": "notes.pdf", "content": "binary-ish"},
        {"name": "../../escape.txt", "content": "From: a@b\nSubject: x\n\nhi\n"},
    ])
    assert saved == 1, "only the .txt should be saved"
    assert skipped == ["notes.pdf"], "the .pdf is reported as skipped"
    # Path traversal in the name must not write outside the working dir.
    written = os.listdir(sess.dir)
    assert written == ["escape.txt"], "name is reduced to a safe basename"
    print("OK - unsupported types skipped and filenames sanitized.")


def test_build_timeline_from_selection():
    sess = web.Session()
    sess.save_uploads(_example_uploads())
    state = sess.state()
    keepers = [f["name"] for f in state["files"] if not f["redundant"]]

    res = sess.build_timeline(keepers)
    assert res["ok"] is True
    assert res["count"] > 0, "the timeline should contain events"
    assert sess.timeline_html and "<html" in sess.timeline_html.lower()
    # Self-contained: no external assets pulled into the rendered page.
    for needle in ('src="http', 'href="http', "<link", "@import"):
        assert needle not in sess.timeline_html, "timeline must stay self-contained"

    empty = sess.build_timeline([])
    assert empty["ok"] is False, "no selection -> nothing to build"
    print("OK - timeline built from %d selected branch(es): %d event(s)."
          % (len(keepers), res["count"]))


def test_file_view_and_compare():
    """The file viewer returns parsed messages keyed for comparison, and a
    redundant file's message keys are a subset of its keeper's — the invariant
    the side-by-side 'why it's redundant' view relies on."""
    sess = web.Session()
    sess.save_uploads(_example_uploads())
    state = sess.state()

    redundant = next(f for f in state["files"] if f["redundant"] and f["coveredBy"])
    keeper = redundant["coveredBy"][0]

    a = sess.file_view(redundant["name"])
    b = sess.file_view(keeper)
    assert a["ok"] and b["ok"], "both files should be viewable"
    assert a["messages"] and all("key" in m and "body" in m for m in a["messages"])

    a_keys = {m["key"] for m in a["messages"]}
    b_keys = {m["key"] for m in b["messages"]}
    assert a_keys <= b_keys, "every message in a redundant file must appear in its keeper"
    assert b_keys - a_keys or any(
        att not in {x.lower() for msg in a["messages"] for x in msg["attachments"]}
        for msg in b["messages"] for att in (x.lower() for x in msg["attachments"])
    ), "the keeper should carry at least one extra message or attachment"

    # Path-safety: a missing or traversing name is rejected, not served.
    assert sess.file_view("does_not_exist.txt")["ok"] is False
    assert sess.file_view("../../secret.txt")["ok"] is False
    print("OK - file viewer: redundant keys subset of keeper; bad names rejected.")


def _post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url):
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


def test_http_round_trip():
    """Exercise the live HTTP surface on an ephemeral port (local only)."""
    httpd = web.run_server(host="127.0.0.1", port=0, open_browser=False)
    try:
        base = "http://127.0.0.1:%d" % httpd.server_address[1]

        assert "<title>Archive Reconstruction Platform" in _get(base + "/")

        state = _post(base + "/api/upload", {"files": _example_uploads()})
        assert state["summary"]["kept"] == 2 and state["summary"]["redundant"] == 4

        keepers = [f["name"] for f in state["files"] if not f["redundant"]]
        built = _post(base + "/api/build", {"selected": keepers})
        assert built["ok"] is True and built["count"] > 0

        fv = json.loads(_get(base + "/api/file?name=" + urllib.parse.quote(keepers[0])))
        assert fv["ok"] is True and fv["messages"], "/api/file returns parsed messages"

        tl = _get(base + "/timeline")
        assert "<html" in tl.lower()

        cleared = _post(base + "/api/reset", {})
        assert cleared["files"] == []
        print("OK - HTTP round-trip: upload -> state -> build -> /timeline served locally.")
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    test_session_matches_dedup_directory()
    test_skips_unsupported_and_sanitizes_names()
    test_build_timeline_from_selection()
    test_file_view_and_compare()
    test_http_round_trip()
    print("OK - local web UI: dedup verdict, selection, and HTTP surface all verified.")
