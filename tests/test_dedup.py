"""Dedup correctness test against the synthetic example threads.

The six example files form two branches and four strict subsets:

* thread_main_full.txt          -- full discussion branch (keep)
* thread_forward_attachment.txt -- branch carrying a unique attachment (keep)
* thread_partial_early.txt      -- subset of both branches (delete)
* thread_partial_mid.txt        -- subset of the full branch (delete)
* thread_forward_noattach.txt   -- subset of the forward branch (delete)
* thread_single_open.txt        -- subset of both branches (delete)

Correct output: keep the 2 branches, recommend deleting the 4 subsets.

Run directly:  python tests/test_dedup.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.dedup import dedup_directory  # noqa: E402

EXPECTED_KEEP = {
    "thread_main_full.txt",
    "thread_forward_attachment.txt",
}
EXPECTED_DELETE = {
    "thread_partial_early.txt",
    "thread_partial_mid.txt",
    "thread_forward_noattach.txt",
    "thread_single_open.txt",
}


def test_branches_and_subsets():
    threads_dir = os.path.join(ROOT, "examples", "threads")
    result = dedup_directory(threads_dir)

    keep = set(result.keep)
    delete = set(result.delete)

    assert keep == EXPECTED_KEEP, f"keep mismatch: got {sorted(keep)}"
    assert delete == EXPECTED_DELETE, f"delete mismatch: got {sorted(delete)}"

    # Every recommended deletion must be covered by at least one kept branch.
    # (It may also be a subset of other redundant files; that is fine and
    # informative, so we only require that a *branch* supersedes it.)
    for report in result.reports:
        if report.redundant:
            assert report.superseded_by, f"{report.name} flagged with no superseder"
            assert EXPECTED_KEEP & set(report.superseded_by), (
                f"{report.name} should be superseded by a kept branch; got {report.superseded_by}"
            )


def test_branches_are_not_subsets_of_each_other():
    """The two branches must each carry content the other lacks."""
    threads_dir = os.path.join(ROOT, "examples", "threads")
    result = dedup_directory(threads_dir)
    by_name = {r.name: r for r in result.reports}

    full = by_name["thread_main_full.txt"].keys
    forward = by_name["thread_forward_attachment.txt"].keys

    assert not full <= forward, "full branch should not be a subset of the forward branch"
    assert not forward <= full, "forward branch should not be a subset of the full branch"
    # The unique attachment is what keeps the forward branch alive.
    assert ("att", "", "safety_case_final.pdf") in forward
    assert ("att", "", "safety_case_final.pdf") not in full


def main():
    test_branches_and_subsets()
    test_branches_are_not_subsets_of_each_other()
    print("OK - kept 2 branches, flagged 4 subsets for deletion.")


if __name__ == "__main__":
    main()
