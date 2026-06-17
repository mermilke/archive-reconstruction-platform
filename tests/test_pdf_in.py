"""Best-effort PDF reading (src/arc/pdf_in.py) + dedup integration.

These tests build small real PDFs whose text is an exported email, in both
uncompressed and FlateDecode-compressed form, and check that:

* the standard-library reader recovers the text (no third-party packages);
* a saved-as-PDF email parses into the same Message a .txt export would;
* two PDF copies of one email dedup to a single keeper;
* a PDF whose name matches an email attachment is treated as an attachment, not
  scanned as its own input;
* an unreadable PDF is skipped (never flagged redundant) and prints the hint.

Run directly:  python tests/test_pdf_in.py
"""
import os
import sys
import tempfile
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc import pdf_in  # noqa: E402
from arc.dedup import dedup_directory  # noqa: E402


def _email_pdf(lines, compress=False):
    """A tiny one-page PDF whose visible text is the given lines (one per line)."""
    ops = ["BT", "/F1 11 Tf", "72 720 Td"]
    for i, ln in enumerate(lines):
        if i:
            ops.append("0 -14 Td")
        esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"({esc}) Tj")
    ops.append("ET")
    content = " ".join(ops).encode("latin-1")
    raw, filt = content, ""
    if compress:
        raw, filt = zlib.compress(content), " /Filter /FlateDecode"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ("<< /Length %d%s >>\nstream\n" % (len(raw), filt)).encode("latin-1")
        + raw + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


EMAIL_A = [
    "From: Raj Patel <raj.patel@voltera.example>",
    "Sent: 2025-11-24 15:30",
    "Subject: RE: Drive Assist 3.0 - canary go/no-go",
    "",
    "Lena, perception rc3 is signed off and engineering is go for the canary. Raj",
]
EMAIL_B = [
    "From: Lena Ortiz <lena.ortiz@voltera.example>",
    "Sent: 2025-11-25 17:40",
    "Subject: RE: Drive Assist 3.0 - canary go/no-go",
    "",
    "Thanks both. Leadership approved the 1% canary for Monday. Lena",
]


def test_stdlib_extracts_uncompressed_and_flate():
    for compress in (False, True):
        text = pdf_in.extract_text(_email_pdf(EMAIL_A, compress=compress))
        assert "perception rc3 is signed off" in text, \
            f"compress={compress} extraction failed: {text!r}"
        assert "From: Raj Patel" in text


def test_saved_as_pdf_parses_into_a_message():
    tmp = tempfile.mkdtemp(prefix="arc-pdf-")
    p = os.path.join(tmp, "email_a.pdf")
    with open(p, "wb") as fh:
        fh.write(_email_pdf(EMAIL_A))
    msgs = pdf_in.parse_pdf(p)
    assert len(msgs) == 1
    assert "raj.patel@voltera.example" in msgs[0].sender
    assert "go for the canary" in msgs[0].body


def test_two_pdf_copies_of_one_email_dedup():
    tmp = tempfile.mkdtemp(prefix="arc-pdf-")
    with open(os.path.join(tmp, "a_copy1.pdf"), "wb") as fh:
        fh.write(_email_pdf(EMAIL_A))                 # same email...
    with open(os.path.join(tmp, "b_copy2.pdf"), "wb") as fh:
        fh.write(_email_pdf(EMAIL_A, compress=True))  # ...re-saved (compressed)
    with open(os.path.join(tmp, "c_other.pdf"), "wb") as fh:
        fh.write(_email_pdf(EMAIL_B))                 # a different email
    result = dedup_directory(tmp)
    assert len(result.reports) == 3
    assert len(result.keep) == 2, f"expected the two copies to collapse: {result.keep}"
    assert len(result.delete) == 1


def test_attachment_named_pdf_is_not_scanned_as_input():
    """A .pdf whose name matches an attachment of a .txt thread stays an
    attachment — it is not scanned as its own document."""
    tmp = tempfile.mkdtemp(prefix="arc-pdf-")
    with open(os.path.join(tmp, "thread.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("From: Raj Patel <raj.patel@voltera.example>\n"
                 "Sent: 2025-11-24 15:30\n"
                 "Subject: Runbook\n"
                 "Attachments: runbook.pdf\n\n"
                 "Runbook attached. Raj\n")
    with open(os.path.join(tmp, "runbook.pdf"), "wb") as fh:
        fh.write(_email_pdf(["Runbook contents here, unrelated text."]))
    scanned = {r.name for r in dedup_directory(tmp).reports}
    assert "runbook.pdf" not in scanned, f"attachment PDF was scanned as input: {scanned}"
    assert "thread.txt" in scanned


def test_unreadable_pdf_is_skipped_and_hints():
    tmp = tempfile.mkdtemp(prefix="arc-pdf-")
    # A structurally-valid-ish PDF with no extractable text operators.
    blank = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
    with open(os.path.join(tmp, "scanned.pdf"), "wb") as fh:
        fh.write(blank)
    pdf_in.NOTES.clear()
    msgs = pdf_in.parse_pdf(os.path.join(tmp, "scanned.pdf"))
    assert msgs == []
    if not pdf_in.have_pypdf():
        assert pdf_in.NOTES, "expected an install-the-extra hint when extraction fails"
        assert "[pdf]" in pdf_in.NOTES[-1]
    # And such a file must not appear (so it's never flagged for deletion).
    assert "scanned.pdf" not in {r.name for r in dedup_directory(tmp).reports}


def test_example_pdf_emails_folder():
    """The committed examples/pdf_emails/ folder mixes every readable format
    (.pdf/.eml/.mbox/.txt) and dedups as documented, format-blind: two PDF copies
    of one email collapse and an .eml of that same email folds in with them; a
    saved thread PDF is kept while an excerpt is flagged; a .mbox archive is a
    fresh branch while a .txt export of one of its messages is a subset."""
    folder = os.path.join(ROOT, "examples", "pdf_emails")
    if not os.path.isdir(folder):
        return  # generated on demand; skip if not present
    result = dedup_directory(folder)
    assert len(result.reports) == 8, "expected 8 files scanned, got %d" % len(result.reports)
    assert len(result.keep) == 4, f"expected 4 kept, got {sorted(result.keep)}"
    assert len(result.delete) == 4, f"expected 4 redundant, got {sorted(result.delete)}"
    by_name = {r.name: r for r in result.reports}
    # Two PDF copies + an .eml of the same email all collapse onto canary_go.pdf.
    assert by_name["canary_go_phone_export.pdf"].redundant
    assert "canary_go.pdf" in by_name["canary_go_phone_export.pdf"].superseded_by
    assert by_name["canary_go_mobile.eml"].redundant, "the .eml copy should fold in cross-format"
    assert "canary_go.pdf" in by_name["canary_go_mobile.eml"].superseded_by
    # Saved thread kept; its excerpt is redundant.
    assert by_name["runbook_excerpt.pdf"].redundant
    assert "runbook_thread.pdf" in by_name["runbook_excerpt.pdf"].superseded_by
    # The .mbox archive is a kept branch; a .txt export of one of its messages
    # is a cross-format subset of it.
    assert not by_name["weekly_sync.mbox"].redundant, "the .mbox archive is a fresh branch"
    assert by_name["safety_case.txt"].redundant
    assert "weekly_sync.mbox" in by_name["safety_case.txt"].superseded_by


def main():
    test_stdlib_extracts_uncompressed_and_flate()
    test_saved_as_pdf_parses_into_a_message()
    test_two_pdf_copies_of_one_email_dedup()
    test_attachment_named_pdf_is_not_scanned_as_input()
    test_unreadable_pdf_is_skipped_and_hints()
    test_example_pdf_emails_folder()
    print("OK - best-effort PDF reading: stdlib extraction (uncompressed + Flate), "
          "saved-as-PDF emails dedup, attachment PDFs stay attachments, unreadable "
          "PDFs are skipped with a hint.")


if __name__ == "__main__":
    main()
