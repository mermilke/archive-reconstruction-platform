"""Dedup correctness test against the mixed-format example archive.

examples/archive/ is the realistic pile: the same Voltera conversations exported
several times across .txt, .eml, and .mbox, with the PDF attachments saved
alongside. It proves the dedup core works *across formats* and that attachments
are first-class:

* an .eml that is a strict subset of a .txt thread is flagged redundant;
* an .mbox that is only a timezone-shifted duplicate of a .txt thread collapses
  to one (timestamps are ignored on purpose);
* a forwarded .eml whose only unique content is a PDF is KEPT (branch-aware);
* the .pdf files in the folder are attachments, not inputs — they are never
  scanned as threads.

Run directly:  python tests/test_archive_example.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.dedup import dedup_directory  # noqa: E402

ARCHIVE = os.path.join(ROOT, "examples", "archive")

EXPECTED_KEEP = {
    "a1_canary_full.txt",
    "a2_perception_thread.mbox",
    "a3_rollout_thread.txt",
    "a3_rollout_runbook.eml",
    "a4_incident_full.txt",
}
EXPECTED_DELETE = {
    "a1_canary_open.eml",
    "a1_canary_mid.txt",
    "a2_perception_plain.txt",
    "a2_perception_early.eml",
    "a3_rollout_open.txt",
    "a4_incident_tzdup.mbox",
    "a4_incident_open.eml",
}


def test_keep_and_delete_across_formats():
    result = dedup_directory(ARCHIVE)
    assert set(result.keep) == EXPECTED_KEEP, "keep mismatch: got %s" % sorted(result.keep)
    assert set(result.delete) == EXPECTED_DELETE, "delete mismatch: got %s" % sorted(result.delete)

    # Every redundant file must be superseded by a kept branch.
    for report in result.reports:
        if report.redundant:
            assert report.superseded_by, "%s flagged with no superseder" % report.name
            assert EXPECTED_KEEP & set(report.superseded_by), (
                "%s should be superseded by a kept branch; got %s"
                % (report.name, report.superseded_by)
            )


def test_pdf_files_are_attachments_not_inputs():
    """The .pdf files in the folder are never scanned as threads (the engine
    reads .txt/.eml/.mbox only), so they appear in no dedup report."""
    result = dedup_directory(ARCHIVE)
    scanned = {r.name for r in result.reports}
    assert not any(n.endswith(".pdf") for n in scanned), \
        "a .pdf was scanned as an input thread: %s" % sorted(scanned)
    assert len(result.reports) == 12, "expected 12 scanned threads, got %d" % len(result.reports)


def test_eml_can_be_a_subset_of_a_txt_thread():
    """Cross-format redundancy: a single-message .eml is a subset of a stacked
    .txt thread that contains that message."""
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}
    open_eml = by_name["a1_canary_open.eml"]
    assert open_eml.redundant
    assert "a1_canary_full.txt" in open_eml.superseded_by


def test_unique_attachment_keeps_a_forward_alive():
    """The forwarded .eml shares its one message with the .txt discussion, but
    its unique PDF attachment means it is NOT a subset of anything — so it is
    kept, and the discussion thread is kept too (neither supersedes the other)."""
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}
    runbook = by_name["a3_rollout_runbook.eml"]
    thread = by_name["a3_rollout_thread.txt"]
    assert not runbook.redundant, "the forward with a unique attachment must be kept"
    assert not thread.redundant
    assert ("att", "", "rollout_runbook_v3.pdf") in runbook.keys
    assert ("att", "", "rollout_runbook_v3.pdf") not in thread.keys


def test_timezone_shifted_duplicate_collapses():
    """An .mbox that differs from a .txt thread only in timezone is redundant —
    identity ignores timestamps."""
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}
    tzdup = by_name["a4_incident_tzdup.mbox"]
    assert tzdup.redundant
    assert "a4_incident_full.txt" in tzdup.superseded_by


def main():
    test_keep_and_delete_across_formats()
    test_pdf_files_are_attachments_not_inputs()
    test_eml_can_be_a_subset_of_a_txt_thread()
    test_unique_attachment_keeps_a_forward_alive()
    test_timezone_shifted_duplicate_collapses()
    print("OK - mixed-format archive: kept 5 branches, flagged 7 redundant across "
          ".txt/.eml/.mbox; PDFs ride along as attachments.")


if __name__ == "__main__":
    main()
