"""Dedup correctness test against the large mixed-format example archive.

examples/archive/ is the realistic pile: a dozen Voltera conversations, each
exported several times across .txt, .eml, and .mbox, with the PDF attachments
saved alongside. It proves the dedup core works *across formats* and that
attachments are first-class.

Filenames encode each file's role (see scripts/generate_example_archive.py):

* branches to KEEP   -> ``*_full`` / ``*_thread`` / ``*_forward``
* redundant SUBSETS  -> ``*_early`` / ``*_mid`` / ``*_open`` / ``*_plain`` / ``*_tzdup``

so this test classifies by suffix rather than hard-coding ~60 names — it keeps
holding as the corpus grows.

Run directly:  python tests/test_archive_example.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.dedup import dedup_directory  # noqa: E402

ARCHIVE = os.path.join(ROOT, "examples", "archive")

KEEP_ROLES = {"full", "thread", "forward"}
SUBSET_ROLES = {"early", "mid", "open", "plain", "tzdup"}


def _role(name):
    """The role suffix: the token before the extension, e.g.
    'c01_perception_open.eml' -> 'open'."""
    return os.path.splitext(name)[0].rsplit("_", 1)[-1]


def test_roles_match_keep_and_delete():
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}

    # Every scanned file's role is one we know about (guards against typos/drift).
    for name in by_name:
        assert _role(name) in KEEP_ROLES | SUBSET_ROLES, "unclassified file: %s" % name

    kept = set(result.keep)
    deleted = set(result.delete)
    for name, report in by_name.items():
        if _role(name) in KEEP_ROLES:
            assert name in kept, "%s is a branch but was flagged redundant" % name
        else:
            assert name in deleted, "%s is a subset but was kept" % name
            # Every redundant file must be superseded by at least one kept branch.
            assert kept & set(report.superseded_by), (
                "%s should be superseded by a kept branch; got %s"
                % (name, report.superseded_by)
            )


def test_counts():
    result = dedup_directory(ARCHIVE)
    assert len(result.reports) == 57, "expected 57 scanned threads, got %d" % len(result.reports)
    assert len(result.keep) == 15, "expected 15 kept branches, got %d" % len(result.keep)
    assert len(result.delete) == 42, "expected 42 redundant files, got %d" % len(result.delete)


def test_pdf_files_are_attachments_not_inputs():
    """The .pdf files in the folder are never scanned as threads (the engine
    reads .txt/.eml/.mbox only), so they appear in no dedup report."""
    result = dedup_directory(ARCHIVE)
    scanned = {r.name for r in result.reports}
    assert not any(n.endswith(".pdf") for n in scanned), \
        "a .pdf was scanned as an input thread: %s" % sorted(scanned)


def test_eml_can_be_a_subset_of_a_txt_thread():
    """Cross-format redundancy: a single-message .eml is a subset of a stacked
    .txt thread that contains that message."""
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}
    open_eml = by_name["c01_perception_open.eml"]
    assert open_eml.redundant
    assert "c01_perception_full.txt" in open_eml.superseded_by


def test_unique_attachment_keeps_a_forward_alive():
    """The forwarded .eml shares its one message with the .txt discussion, but
    its unique PDF attachment means it is NOT a subset of anything — so it is
    kept, and the discussion thread is kept too (neither supersedes the other)."""
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}
    forward = by_name["c01_perception_forward.eml"]
    full = by_name["c01_perception_full.txt"]
    assert not forward.redundant, "the forward with a unique attachment must be kept"
    assert not full.redundant
    assert ("att", "", "c01_perception_eval.pdf") in forward.keys
    assert ("att", "", "c01_perception_eval.pdf") not in full.keys


def test_attachment_carrying_thread_supersedes_its_plain_copy():
    """When the .mbox thread itself carries the PDF, the plain .txt re-export of
    the same messages (no attachment) is a subset and is flagged redundant."""
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}
    thread = by_name["c02_canary_thread.mbox"]
    plain = by_name["c02_canary_plain.txt"]
    assert not thread.redundant
    assert plain.redundant
    assert "c02_canary_thread.mbox" in plain.superseded_by


def test_timezone_shifted_duplicate_collapses():
    """An .mbox that differs from a thread only in timezone (and drops the last
    message) is redundant — identity ignores timestamps."""
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}
    tzdup = by_name["c04_incident_tzdup.mbox"]
    assert tzdup.redundant
    assert "c04_incident_full.mbox" in tzdup.superseded_by


def main():
    test_roles_match_keep_and_delete()
    test_counts()
    test_pdf_files_are_attachments_not_inputs()
    test_eml_can_be_a_subset_of_a_txt_thread()
    test_unique_attachment_keeps_a_forward_alive()
    test_attachment_carrying_thread_supersedes_its_plain_copy()
    test_timezone_shifted_duplicate_collapses()
    print("OK - mixed-format archive: 57 threads -> kept 15 branches, flagged 42 "
          "redundant across .txt/.eml/.mbox; 7 PDFs ride along as attachments.")


if __name__ == "__main__":
    main()
