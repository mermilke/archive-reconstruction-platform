#!/usr/bin/env python3
"""Generate examples/pdf_emails/ — saved emails in *every* readable format.

This is the one folder to drag into `arc web` (or run
`arc dedup examples/pdf_emails`) to see the whole input story at once: the
best-effort PDF reader, real `.eml`/`.mbox`, and a plain `.txt` export — all
deduped together. It shows that branch-aware dedup is format-blind:

* two PDF copies of one email collapse, and an `.eml` of that *same* email
  folds in with them (cross-format, equal key-sets);
* a saved multi-message thread PDF is kept, an excerpt of it is redundant;
* a `.mbox` archive of two new messages is a fresh branch (kept), and a `.txt`
  export of one of those messages is a subset of the archive (redundant).

The PDFs are real one-page files with selectable text (uncompressed and
FlateDecode), so the standard-library reader handles them with zero
dependencies. The `.eml`/`.mbox` are built with the stdlib email/mailbox
modules. All content is fully synthetic (Voltera / Drive Assist 3.0).

Run:  python scripts/generate_pdf_examples.py
"""
import datetime
import email.policy
import email.utils
import mailbox
import os
import zlib
from email.message import EmailMessage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "examples", "pdf_emails")

RAJ = "Raj Patel <raj.patel@voltera.example>"
LENA = "Lena Ortiz <lena.ortiz@voltera.example>"
PRIYA = "Priya Iyer <priya.iyer@voltera.example>"
AISHA = "Aisha Bello <aisha.bello@voltera.example>"
DANA = "Dana Olsen <dana.olsen@voltera.example>"


def _msg_lines(sender, date, subject, body):
    return ["From: %s" % sender, "Sent: %s" % date, "Subject: %s" % subject, "", body, ""]


def _dt(y, mo, d, h, mi):
    tz = datetime.timezone(datetime.timedelta(hours=-8))
    return datetime.datetime(y, mo, d, h, mi, tzinfo=tz)


def _eml(sender, when, subject, body):
    """A valid one-message .eml built with the stdlib email module."""
    msg = EmailMessage(policy=email.policy.default)
    msg["From"] = sender
    msg["To"] = LENA
    msg["Date"] = email.utils.format_datetime(when)
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


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


def _write_eml(name, msg):
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(msg.as_bytes())


def _write_mbox(name, msgs):
    path = os.path.join(OUT, name)
    box = mailbox.mbox(path)
    box.lock()
    try:
        for msg in msgs:
            box.add(mailbox.mboxMessage(msg.as_bytes()))
        box.flush()
    finally:
        box.unlock()
        box.close()


def _write_text(name, lines):
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


# Canonical bodies (defined once so cross-format copies share dedup identity).
GO_SUBJECT = "RE: Drive Assist 3.0 - canary go/no-go"
GO_BODY = "Lena, perception rc3 is signed off and engineering is go for the canary. Raj"
SAFETY_SUBJECT = "Drive Assist 3.0 - safety case signed"
SAFETY_BODY = ("Safety leadership signed the case for the staged rollout; the residual-risk "
               "items are all closed out. Aisha")
SYNC_SUBJECT = "Drive Assist 3.0 - weekly program sync"
SYNC_BODY = ("Weekly program sync: the canary is holding at target and ring 2 is scheduled "
             "once telemetry clears the 24-hour gate. Dana")

# Canonical messages (defined once so copies share identity).
GO = _msg_lines(RAJ, "2025-11-24 15:30", GO_SUBJECT, GO_BODY)
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
    # The SAME email exported as .eml folds in with the two PDFs (cross-format).
    # ".pdf" sorts before "_mobile.eml" ('.' < '_'), so canary_go.pdf stays the
    # keeper and this .eml is flagged redundant alongside the phone export.
    _write_eml("canary_go_mobile.eml", _eml(RAJ, _dt(2025, 11, 24, 15, 30), GO_SUBJECT, GO_BODY))
    # A different email — kept.
    write_pdf("leadership_approval.pdf", APPROVAL)
    # A saved multi-message thread — kept — and an excerpt of it — redundant.
    write_pdf("runbook_thread.pdf", RUN1 + RUN2 + RUN3)
    write_pdf("runbook_excerpt.pdf", RUN1, compress=True)
    # A .mbox archive of two new messages — a fresh branch, kept.
    _write_mbox("weekly_sync.mbox", [
        _eml(AISHA, _dt(2025, 9, 19, 11, 15), SAFETY_SUBJECT, SAFETY_BODY),
        _eml(DANA, _dt(2025, 12, 8, 9, 0), SYNC_SUBJECT, SYNC_BODY),
    ])
    # A plain .txt export of one of those messages — a subset of the archive,
    # so it is flagged redundant (cross-format subset).
    _write_text("safety_case.txt", _msg_lines(AISHA, "2025-09-19 11:15", SAFETY_SUBJECT, SAFETY_BODY))

    files = [f for f in sorted(os.listdir(OUT)) if f != "README.md"]
    print("Wrote %d saved email file(s) to %s" % (len(files), OUT))
    for f in files:
        print("  " + f)


if __name__ == "__main__":
    main()
