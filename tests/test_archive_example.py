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
        assert _role(name) in KEEP_ROLES | SUBSET_ROLES, "unclassified file: %s" % name

    kept = set(result.keep)
    for name, report in by_name.items():
        if _role(name) in KEEP_ROLES:
            assert name in kept, "%s is a branch but was flagged redundant" % name
        else:
            assert report.redundant, "%s is a subset but was kept" % name
            assert kept & set(report.superseded_by), (
                "%s should be superseded by a kept branch; got %s"
                % (name, report.superseded_by)
            )


def test_counts():
    result = dedup_directory(ARCHIVE)
    assert len(result.reports) == 73, "expected 73 scanned threads, got %d" % len(result.reports)
    assert len(result.keep) == 23, "expected 23 kept branches, got %d" % len(result.keep)
    assert len(result.delete) == 50, "expected 50 redundant files, got %d" % len(result.delete)


def test_pdf_and_binary_files_are_attachments_not_inputs():
    """The .pdf/.csv/.png files in the folder are never scanned as threads (the
    engine reads .txt/.eml/.mbox only), so they appear in no dedup report."""
    scanned = set(_reports())
    assert not any(n.endswith((".pdf", ".csv", ".png")) for n in scanned), \
        "a non-thread file was scanned as input: %s" % sorted(scanned)


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
        assert not r[branch].redundant, "%s must be kept" % branch
    # The opener, exported alone, is a subset of all three branches.
    assert r["c11_threeway_open.eml"].redundant
    assert "c11_threeway_brancha.txt" in r["c11_threeway_open.eml"].superseded_by


def test_normalization_collapses_requoted_signed_and_html_reexports():
    """The same message re-exported with a quoted-reply tail, a ``-- ``
    signature, or as an HTML-only body all fold back onto the plain thread."""
    r = _reports()
    for variant in ("c12_normalize_quoted.eml", "c12_normalize_sig.eml",
                    "c12_normalize_html.eml"):
        assert r[variant].redundant, "%s should normalize to a subset" % variant
        assert "c12_normalize_full.txt" in r[variant].superseded_by, (
            "%s should be superseded by the plain thread" % variant)


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


def main():
    test_roles_match_keep_and_delete()
    test_counts()
    test_pdf_and_binary_files_are_attachments_not_inputs()
    test_eml_can_be_a_subset_of_a_txt_thread()
    test_three_way_branch_keeps_every_fork()
    test_normalization_collapses_requoted_signed_and_html_reexports()
    test_attachment_branching_keeps_both_attachment_sets()
    test_attachment_carrying_thread_supersedes_its_plain_copy()
    test_timezone_shifted_duplicate_collapses()
    test_large_mbox_is_kept_as_its_own_branch()
    print("OK - mixed-format archive: 73 threads -> 23 kept branches, 50 redundant; "
          "covers 3-way forks, normalization collapse, attachment branching, and a "
          "large .mbox, with .pdf/.csv/.png attachments riding along.")


if __name__ == "__main__":
    main()
