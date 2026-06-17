"""Dedup correctness test against the large mixed-format example archive.

examples/archive/ is the realistic pile: many Voltera conversations, each
exported several times across .txt, .eml, and .mbox, with the attachments saved
alongside. It proves the dedup core works *across formats*, that normalization
collapses re-exports of the same message, that a fork keeps every branch, and
that attachments are first-class.

Filenames encode each file's role (see scripts/generate_example_archive.py):

* branches to KEEP   -> ``*_full`` / ``*_thread`` / ``*_forward`` /
                        ``*_branch[abc]`` / ``*_att[ab]``
* redundant SUBSETS  -> ``*_early`` / ``*_mid`` / ``*_open`` / ``*_plain`` /
                        ``*_tzdup`` / ``*_quoted`` / ``*_sig`` / ``*_html``

so this test classifies by role rather than hard-coding ~70 names — it keeps
holding as the corpus grows.

Run directly:  python tests/test_archive_example.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.dedup import dedup_directory  # noqa: E402

ARCHIVE = os.path.join(ROOT, "examples", "archive")

KEEP_ROLES = {"full", "thread", "forward", "brancha", "branchb", "branchc", "atta", "attb"}
SUBSET_ROLES = {"early", "mid", "open", "plain", "tzdup", "quoted", "sig", "html"}


def _role(name):
    """The role suffix: the token before the extension, e.g.
    'c01_perception_open.eml' -> 'open'."""
    return os.path.splitext(name)[0].rsplit("_", 1)[-1]


def _reports():
    return {r.name: r for r in dedup_directory(ARCHIVE).reports}


def test_roles_match_keep_and_delete():
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}

    for name in by_name:  # guard against typos / unclassified files
        assert _role(name) in KEEP_ROLES | SUBSET_ROLES, f"unclassified file: {name}"

    kept = set(result.keep)
    for name, report in by_name.items():
        if _role(name) in KEEP_ROLES:
            assert name in kept, f"{name} is a branch but was flagged redundant"
        else:
            assert report.redundant, f"{name} is a subset but was kept"
            assert kept & set(report.superseded_by), (
                f"{name} should be superseded by a kept branch; got {report.superseded_by}"
            )


def test_counts():
    """Counts are *derived from the corpus* (by filename role), not hard-coded, so
    adding or removing a fixture can't silently rot a magic number — the keep set
    must equal exactly the branch-role files, and delete the subset-role files."""
    result = dedup_directory(ARCHIVE)
    by_name = {r.name: r for r in result.reports}
    expected_keep = {n for n in by_name if _role(n) in KEEP_ROLES}
    expected_delete = {n for n in by_name if _role(n) in SUBSET_ROLES}

    assert len(result.reports) == len(expected_keep) + len(expected_delete), (
        "every scanned file should be either a branch or a subset")
    assert set(result.keep) == expected_keep, (
        "kept branches should be exactly the branch-role files")
    assert set(result.delete) == expected_delete, (
        "redundant files should be exactly the subset-role files")


def test_attachment_files_stay_attachments_but_saved_pdf_emails_are_read():
    """A .pdf/.csv/.png named as another message's *attachment* rides along
    matched by name and is never scanned as input. But an email genuinely
    *saved/printed to PDF* (the c15/c16 files) is read by the best-effort PDF
    reader and deduped like any other export."""
    scanned = set(_reports())
    # .csv/.png are only ever attachments — never scanned as input.
    assert not any(n.endswith((".csv", ".png")) for n in scanned), \
        f"a binary attachment was scanned as input: {sorted(scanned)}"
    # A .pdf named as another message's attachment stays an attachment...
    for att_pdf in ("c01_perception_eval.pdf", "c03_runbook_v3.pdf", "spec_v1.pdf"):
        assert att_pdf not in scanned, f"attachment PDF scanned as input: {att_pdf}"
    # ...but an email saved/printed to PDF is read and deduped.
    for saved_pdf in ("c15_pdfsaved_open.pdf", "c15_pdfsaved_early.pdf",
                      "c16_pdfonly_full.pdf"):
        assert saved_pdf in scanned, f"saved-to-PDF email was not read: {saved_pdf}"


def test_eml_can_be_a_subset_of_a_txt_thread():
    """Cross-format redundancy: a single-message .eml is a subset of a stacked
    .txt thread that contains that message."""
    open_eml = _reports()["c01_perception_open.eml"]
    assert open_eml.redundant
    assert "c01_perception_full.txt" in open_eml.superseded_by


def test_three_way_branch_keeps_every_fork():
    """Three exports of one conversation, each holding a reply the others lack:
    none is a subset of another, so all three are kept (the clearest case that
    'keep the biggest file' loses data)."""
    r = _reports()
    for branch in ("c11_threeway_brancha.txt", "c11_threeway_branchb.mbox",
                   "c11_threeway_branchc.txt"):
        assert not r[branch].redundant, f"{branch} must be kept"
    # The opener, exported alone, is a subset of all three branches.
    assert r["c11_threeway_open.eml"].redundant
    assert "c11_threeway_brancha.txt" in r["c11_threeway_open.eml"].superseded_by


def test_normalization_collapses_requoted_signed_and_html_reexports():
    """The same message re-exported with a quoted-reply tail, a ``-- ``
    signature, or as an HTML-only body all fold back onto the plain thread."""
    r = _reports()
    for variant in ("c12_normalize_quoted.eml", "c12_normalize_sig.eml",
                    "c12_normalize_html.eml"):
        assert r[variant].redundant, f"{variant} should normalize to a subset"
        assert "c12_normalize_full.txt" in r[variant].superseded_by, (
            f"{variant} should be superseded by the plain thread")


def test_attachment_branching_keeps_both_attachment_sets():
    """Two files share their messages but carry different attachments — both are
    kept; the plain copy (no attachments) is the only redundant one; a forward
    with a unique attachment is kept too."""
    r = _reports()
    assert not r["c13_assets_atta.txt"].redundant
    assert not r["c13_assets_attb.eml"].redundant
    assert not r["c13_assets_forward.eml"].redundant
    plain = r["c13_assets_plain.txt"]
    assert plain.redundant
    assert "c13_assets_atta.txt" in plain.superseded_by
    assert ("att", "", "launch_budget.csv") in r["c13_assets_forward.eml"].keys


def test_attachment_carrying_thread_supersedes_its_plain_copy():
    r = _reports()
    assert not r["c02_canary_thread.mbox"].redundant
    plain = r["c02_canary_plain.txt"]
    assert plain.redundant
    assert "c02_canary_thread.mbox" in plain.superseded_by


def test_timezone_shifted_duplicate_collapses():
    r = _reports()
    tzdup = r["c04_incident_tzdup.mbox"]
    assert tzdup.redundant
    assert "c04_incident_full.mbox" in tzdup.superseded_by


def test_large_mbox_is_kept_as_its_own_branch():
    r = _reports()
    assert not r["c14_mailbox_full.mbox"].redundant


def test_saved_to_pdf_email_is_a_cross_format_subset_of_a_txt_thread():
    """An email saved/printed to PDF is read by the best-effort PDF reader and
    recognized as a subset of the .txt thread that contains those messages."""
    r = _reports()
    for excerpt in ("c15_pdfsaved_open.pdf", "c15_pdfsaved_early.pdf"):
        assert r[excerpt].redundant, f"{excerpt} should be read and flagged redundant"
        assert "c15_pdfsaved_full.txt" in r[excerpt].superseded_by, (
            f"{excerpt} should be superseded by the .txt thread")


def test_pdf_only_conversation_is_read_and_kept_as_a_branch():
    """A conversation that exists ONLY as a saved PDF is read from the PDF and
    kept as its own branch — proof a saved-to-PDF email isn't silently lost."""
    assert not _reports()["c16_pdfonly_full.pdf"].redundant


def main():
    test_roles_match_keep_and_delete()
    test_counts()
    test_attachment_files_stay_attachments_but_saved_pdf_emails_are_read()
    test_eml_can_be_a_subset_of_a_txt_thread()
    test_three_way_branch_keeps_every_fork()
    test_normalization_collapses_requoted_signed_and_html_reexports()
    test_attachment_branching_keeps_both_attachment_sets()
    test_attachment_carrying_thread_supersedes_its_plain_copy()
    test_timezone_shifted_duplicate_collapses()
    test_large_mbox_is_kept_as_its_own_branch()
    test_saved_to_pdf_email_is_a_cross_format_subset_of_a_txt_thread()
    test_pdf_only_conversation_is_read_and_kept_as_a_branch()
    result = dedup_directory(ARCHIVE)
    print("OK - mixed-format archive: %d threads -> %d kept branches, %d redundant; "
          "covers 3-way forks, normalization collapse, attachment branching, a large "
          ".mbox, and emails saved/printed to PDF read as inputs, with .pdf/.csv/.png "
          "attachments riding along."
          % (len(result.reports), len(result.keep), len(result.delete)))


if __name__ == "__main__":
    main()
