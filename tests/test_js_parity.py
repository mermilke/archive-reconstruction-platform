"""Parity test: the in-browser JS dedup port must agree with the Python core.

The web demo (docs/try.html) runs a JavaScript port of the dedup algorithm
(docs/arc-dedup.js) so visitors can use the tool with no install. That port is a
*second* implementation of the crown-jewel logic, so it can drift from the
Python original. This test pins them together: it runs the JS port over the
canonical example corpus (via tests/js-parity-driver.js under Node) and asserts
its keep/delete verdict and dedup counts match `arc dedup` exactly.

If Node isn't installed, the test SKIPS (prints a notice, exits 0) rather than
failing — the JS port is a front-end convenience, not a build requirement.

Run directly:  python tests/test_js_parity.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.bridge import collect_unique_messages  # noqa: E402
from arc.dedup import dedup_directory  # noqa: E402
from arc.parse import find_message_files  # noqa: E402

THREADS_DIR = os.path.join(ROOT, "examples", "threads")
DRIVER = os.path.join(ROOT, "tests", "js-parity-driver.js")


def _run_js(directory):
    """Run the JS port over a folder; return its parsed JSON verdict."""
    proc = subprocess.run(
        ["node", DRIVER, directory],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise AssertionError("JS driver failed (%d):\n%s" % (proc.returncode, proc.stderr))
    return json.loads(proc.stdout)


def test_js_matches_python_on_examples():
    py = dedup_directory(THREADS_DIR)
    js = _run_js(THREADS_DIR)

    assert set(js["keep"]) == set(py.keep), (
        "keep mismatch — JS %s vs Python %s" % (sorted(js["keep"]), sorted(py.keep))
    )
    assert set(js["delete"]) == set(py.delete), (
        "delete mismatch — JS %s vs Python %s" % (sorted(js["delete"]), sorted(py.delete))
    )

    # Per-file redundant flag must agree, file by file.
    py_redundant = {r.name: r.redundant for r in py.reports}
    js_redundant = {f["name"]: f["redundant"] for f in js["files"]}
    assert js_redundant == py_redundant, (
        "per-file verdict mismatch — JS %s vs Python %s" % (js_redundant, py_redundant)
    )


def _assert_verdict_parity(directory):
    """Run Python and the JS port over a folder; assert identical verdicts."""
    py = dedup_directory(directory)
    js = _run_js(directory)
    assert set(js["keep"]) == set(py.keep), (
        "keep mismatch in %s — JS %s vs Python %s"
        % (directory, sorted(js["keep"]), sorted(py.keep))
    )
    assert set(js["delete"]) == set(py.delete), (
        "delete mismatch in %s — JS %s vs Python %s"
        % (directory, sorted(js["delete"]), sorted(py.delete))
    )


def test_js_matches_python_on_quote_stripped_bodies():
    """The same message pasted clean vs. with a quoted-reply tail must collapse to
    one keeper in *both* implementations — this exercises the normalize port
    (attribution detection + quote stripping), which the clean example corpus
    doesn't. A drift in the JS normalizer would change the fingerprint and split
    the pair, so the verdicts would diverge here.
    """
    clean = (
        "From: Raj Patel <raj.patel@voltera.example>\n"
        "Sent: 2025-01-02 10:00\n"
        "Subject: RE: Plan\n"
        "\n"
        "Sounds good, shipping Friday.\n"
    )
    with_quote_tail = (
        "From: Raj Patel <raj.patel@voltera.example>\n"
        "Sent: 2025-01-02 11:30\n"          # different timestamp — must be ignored
        "Subject: RE: Plan\n"
        "\n"
        "Sounds good, shipping Friday.\n"
        "\n"
        "On Thu, Jan 1, 2025 at 9:00 AM Lena Ortiz <lena.ortiz@voltera.example> wrote:\n"
        "> Are we still on for Friday?\n"
    )
    tmp = tempfile.mkdtemp(prefix="arc-js-parity-")
    try:
        # "a_clean" sorts before "b_quoted", so the clean file is the keeper.
        with open(os.path.join(tmp, "a_clean.txt"), "w", encoding="utf-8", newline="") as fh:
            fh.write(clean)
        with open(os.path.join(tmp, "b_quoted.txt"), "w", encoding="utf-8", newline="") as fh:
            fh.write(with_quote_tail)

        # Sanity: Python must see these as duplicates (so the case is meaningful).
        py = dedup_directory(tmp)
        assert set(py.keep) == {"a_clean.txt"}, "setup: expected clean file kept, got %s" % py.keep
        assert set(py.delete) == {"b_quoted.txt"}, "setup: expected quoted file redundant, got %s" % py.delete

        _assert_verdict_parity(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_js_summary_counts_match_python():
    js = _run_js(THREADS_DIR)
    paths = find_message_files(THREADS_DIR)
    uniques, total = collect_unique_messages(paths)

    assert js["summary"]["uniqueMessages"] == len(uniques), (
        "unique-message count mismatch — JS %d vs Python %d"
        % (js["summary"]["uniqueMessages"], len(uniques))
    )
    assert js["summary"]["duplicates"] == max(0, total - len(uniques)), (
        "duplicate count mismatch — JS %d vs Python %d"
        % (js["summary"]["duplicates"], max(0, total - len(uniques)))
    )
    assert js["summary"]["files"] == len(paths)


def main():
    if shutil.which("node") is None:
        print("SKIP - Node.js not found; the JS dedup port is a front-end "
              "convenience and is not required for the Python toolkit.")
        return 0
    test_js_matches_python_on_examples()
    test_js_matches_python_on_quote_stripped_bodies()
    test_js_summary_counts_match_python()
    print("OK - JS dedup port matches the Python core (examples + quote-stripping).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
