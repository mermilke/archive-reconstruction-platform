"""Run every ``tests/test_*.py`` and report a pass/fail summary.

Each test file is a self-contained script (it adds ``src`` to ``sys.path`` and
runs its checks under ``if __name__ == "__main__"``), so the simplest, most
faithful runner just executes each one with the current interpreter and collects
the exit codes. No third-party test framework — stdlib only, like the toolkit.

    python tests/run_all.py          # run the whole suite
    python tests/run_all.py -q       # quiet: only show failures + summary

Exit code is 0 only if every test file passed.
"""
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# Per-test-file wall-clock cap. The suite spins up a live local web server and a
# Node subprocess (parity test); a hang in either shouldn't wedge the whole run
# with no diagnostic. Generous — the whole suite finishes in a few seconds.
TIMEOUT = 300


def main(argv):
    quiet = "-q" in argv or "--quiet" in argv
    test_files = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
    if not test_files:
        print(f"No test files found in {HERE}")
        return 1

    # When measuring coverage, each test runs as a subprocess, so wrap the child
    # interpreter with `coverage run` (parallel-mode writes a separate data file
    # per process; combine them afterwards). Triggered by the standard
    # COVERAGE_PROCESS_START env var so a plain run stays dependency-free.
    measure = bool(os.environ.get("COVERAGE_PROCESS_START"))

    failures = []
    start = time.time()
    for path in test_files:
        name = os.path.basename(path)
        if measure:
            cmd = [sys.executable, "-m", "coverage", "run", "--parallel-mode", path]
        else:
            cmd = [sys.executable, path]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            failures.append(name)
            print(f"[TIMEOUT] {name} (exceeded {TIMEOUT}s)")
            out = ((exc.stdout or "") + (exc.stderr or "")).strip()
            if out:
                print("\n".join("    " + line for line in out.splitlines()))
            continue
        ok = proc.returncode == 0
        if not ok:
            failures.append(name)
        if not quiet or not ok:
            mark = "PASS" if ok else "FAIL"
            print(f"[{mark}] {name}")
            if not ok:
                # Surface the failing test's output so the cause is visible.
                out = (proc.stdout + proc.stderr).strip()
                if out:
                    print("\n".join("    " + line for line in out.splitlines()))

    elapsed = time.time() - start
    total = len(test_files)
    passed = total - len(failures)
    print("\n%d/%d test file(s) passed in %.2fs." % (passed, total, elapsed))
    if failures:
        print("Failed: {}".format(", ".join(failures)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
