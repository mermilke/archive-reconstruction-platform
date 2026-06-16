#!/usr/bin/env python3
"""Generate examples/pdf_emails/ — a few emails "saved/printed to PDF".

This is the folder to drag into `arc web` (or run `arc dedup examples/pdf_emails`)
to see the best-effort PDF reader at work: two PDF copies of one email collapse,
a saved multi-message thread is kept, and an excerpt of it is flagged redundant.
The PDFs are real one-page files with selectable text (uncompressed and
FlateDecode), so the standard-library reader handles them with zero
dependencies. All content is fully synthetic (Voltera / Drive Assist 3.0).

Run:  python scripts/generate_pdf_examples.py
"""
import os
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "examples", "pdf_emails")

RAJ = "Raj Patel <raj.patel@voltera.example>"
LENA = "Lena Ortiz <lena.ortiz@voltera.example>"
PRIYA = "Priya Iyer <priya.iyer@voltera.example>"


def _msg_lines(sender, date, subject, body):
    return ["From: %s" % sender, "Sent: %s" % date, "Subject: %s" % subject, "", body, ""]


def _text_pdf(lines, compress=False):
    """A one-page PDF whose visible text is ``lines`` (one per source line)."""
    ops = ["BT", "/F1 11 Tf", "72 730 Td"]
    for i, ln in enumerate(lines):
        if i:
            ops.append("0 -14 Td")
        esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append("(%s) Tj" % esc)
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
        ("<< /Length %d%s >>\nstream\n" % (len(raw), filt)).encode("latin-1") + raw + b"\nendstream",
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


def write_pdf(name, lines, compress=False):
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(_text_pdf(lines, compress=compress))


# Canonical messages (defined once so copies share identity).
GO = _msg_lines(RAJ, "2025-11-24 15:30", "RE: Drive Assist 3.0 - canary go/no-go",
                "Lena, perception rc3 is signed off and engineering is go for the canary. Raj")
APPROVAL = _msg_lines(LENA, "2025-11-25 17:40", "RE: Drive Assist 3.0 - canary go/no-go",
                      "Thanks both. Leadership approved the 1% canary for Monday. Lena")
RUN1 = _msg_lines(RAJ, "2025-12-01 09:30", "Drive Assist 3.0 - staged rollout runbook",
                  "Runbook for the staged rollout attached; the auto-halt trips past the beta baseline. Raj")
RUN2 = _msg_lines(PRIYA, "2025-12-01 13:00", "RE: Drive Assist 3.0 - staged rollout runbook",
                  "Comms is ready with a launch-day story and a holding statement. Priya")
RUN3 = _msg_lines(LENA, "2025-12-02 08:45", "RE: Drive Assist 3.0 - staged rollout runbook",
                  "Approved the ring plan: 1, 10, 50, 100 percent, each gated on telemetry. Lena")


def main():
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            if f != "README.md":
                os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)

    # Two PDF copies of the same email — one re-saved (compressed) — collapse.
    write_pdf("canary_go.pdf", GO)
    write_pdf("canary_go_phone_export.pdf", GO, compress=True)
    # A different email — kept.
    write_pdf("leadership_approval.pdf", APPROVAL)
    # A saved multi-message thread — kept — and an excerpt of it — redundant.
    write_pdf("runbook_thread.pdf", RUN1 + RUN2 + RUN3)
    write_pdf("runbook_excerpt.pdf", RUN1, compress=True)

    files = [f for f in sorted(os.listdir(OUT)) if f != "README.md"]
    print("Wrote %d PDF email(s) to %s" % (len(files), OUT))
    for f in files:
        print("  " + f)


if __name__ == "__main__":
    main()
