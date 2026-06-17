"""CLI surface tests: argument dispatch and exit codes for `arc`.

cli.py is the thin entry point the library-level tests bypass (they call the
modules directly). These drive main(argv) end-to-end — capturing stdout — for
the reachable exit codes and the cp1252-safe ASCII helper that exists purely for
Windows consoles.

Run directly:  python tests/test_cli.py
"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.cli import _ascii  # noqa: E402
from arc.cli import main as cli_main  # noqa: E402

THREADS = os.path.join(ROOT, "examples", "threads")
RAW_EMAIL = os.path.join(ROOT, "examples", "raw_email")
EVENTS_JSON = os.path.join(ROOT, "examples", "events.json")


def _run(argv):
    """Run the CLI, returning (exit_code, captured_stdout)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli_main(argv)
    return code, buf.getvalue()


def test_version_exits_zero():
    try:
        _run(["--version"])
    except SystemExit as exc:  # argparse prints the version, then exits 0
        assert exc.code == 0
    else:
        raise AssertionError("--version should raise SystemExit")


def test_missing_subcommand_errors():
    try:
        _run([])
    except SystemExit as exc:  # required subparser missing -> argparse exit 2
        assert exc.code == 2
    else:
        raise AssertionError("a missing subcommand should raise SystemExit(2)")


def test_dedup_keeps_two_branches_exit_zero():
    code, out = _run(["dedup", THREADS])
    assert code == 0
    assert "KEEP" in out and "DELETE" in out
    assert "thread_main_full.txt" in out
    assert "no files were deleted" in out.lower()


def test_dedup_no_match_returns_one():
    code, _out = _run(["dedup", THREADS, "--pattern", "*.no-such-ext"])
    assert code == 1


def test_tree_verifies_no_loss_exit_zero():
    code, out = _run(["tree", RAW_EMAIL])
    assert code == 0
    # The benchmark line always reports the loss count; here it must be zero.
    assert "0 lost" in out.lower()


def test_timeline_writes_html_exit_zero():
    with tempfile.TemporaryDirectory() as d:
        out_path = os.path.join(d, "tl.html")
        code, out = _run(["timeline", EVENTS_JSON, "-o", out_path])
        assert code == 0
        assert os.path.exists(out_path)
        assert "Wrote" in out


def test_ascii_helper_survives_a_windows_codepage():
    """Subjects can carry Unicode (em-dash, non-breaking hyphen, emoji); CLI
    output must reduce to pure ASCII so a cp1252 console never raises."""
    safe = _ascii("Voltera — go/no‑go ✅")
    assert safe == str(safe).encode("ascii", "replace").decode("ascii")
    assert all(ord(c) < 128 for c in safe)


def main():
    test_version_exits_zero()
    test_missing_subcommand_errors()
    test_dedup_keeps_two_branches_exit_zero()
    test_dedup_no_match_returns_one()
    test_tree_verifies_no_loss_exit_zero()
    test_timeline_writes_html_exit_zero()
    test_ascii_helper_survives_a_windows_codepage()
    print("OK - cli: dedup/tree/timeline dispatch, exit codes (0/1/2), and ASCII-safe output.")


if __name__ == "__main__":
    main()
