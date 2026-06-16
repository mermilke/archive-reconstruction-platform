#!/usr/bin/env python3
"""Generate examples/archive/ — a realistic, mixed-format export pile.

Where examples/threads/ is the minimal teaching fixture (six .txt files, the
canonical "keep 2, delete 4" case the tests pin), examples/archive/ is the
*messy real-world pile* you actually get after archiving a mailbox: the same
conversations exported several times over, in different formats, with the PDF
attachments saved right alongside the threads.

It exercises everything the dedup core handles:

* three input formats in one folder — ``.txt`` stacked exports, real ``.eml``
  messages, and ``.mbox`` archives — deduped together;
* cross-format redundancy — an ``.eml`` that is a strict subset of a ``.txt``
  thread, and an ``.mbox`` that is a timezone-shifted duplicate of a ``.txt``
  (collapsed to one, because timestamps are deliberately ignored);
* attachment-driven keeps — a forwarded ``.eml`` whose only unique content is a
  PDF is never marked redundant (the branch-aware crown jewel);
* PDFs as first-class attachments — the real ``.pdf`` files sit in the folder
  too. The dedup engine reads ``.txt``/``.eml``/``.mbox`` (stdlib only, zero
  dependencies) and treats each attachment by *name*; the PDFs themselves are
  not parsed as inputs, they ride along as attachments.

Everything is fully synthetic — a fictional EV company, Voltera, rolling out a
"Drive Assist 3.0" feature — matching the rest of the sample data.

Run:  python scripts/generate_example_archive.py
"""
import email.utils
import mailbox
import os
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_sample_events import _minimal_pdf  # noqa: E402  (reuse the PDF builder)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "examples", "archive")

LENA = "Lena Ortiz <lena.ortiz@voltera.example>"
RAJ = "Raj Patel <raj.patel@voltera.example>"
PRIYA = "Priya Iyer <priya.iyer@voltera.example>"
TOMAS = "Tomas Vidal <tomas.vidal@voltera.example>"
SOFIA = "Sofia Marenko <sofia.marenko@voltera.example>"
NORA = "Nora Fischer <nora.fischer@voltera.example>"

# Canonical messages, each defined ONCE and reused across every file it appears
# in, so the same message has a byte-identical body everywhere — that is what
# lets dedup recognize the copies as one message. Identity is sender + body;
# timestamps and attachment names are handled separately.
#   key -> (sender, recipient, subject, "YYYY-MM-DD HH:MM", body)
M = {
    # Conversation 1 — canary go/no-go
    "c1m1": (LENA, RAJ, "Drive Assist 3.0 - canary go/no-go", "2025-11-24 09:00",
             "Raj, are we go for the 1% canary next week? I need perception rc3 and the "
             "safety case both signed off before I brief leadership. Lena"),
    "c1m2": (RAJ, LENA, "RE: Drive Assist 3.0 - canary go/no-go", "2025-11-24 15:30",
             "Lena, perception rc3 is signed off and the release candidate build is cut. "
             "From engineering we are go for the canary. Raj"),
    "c1m3": (PRIYA, LENA, "RE: Drive Assist 3.0 - canary go/no-go", "2025-11-25 08:15",
             "Support is staffed for the canary window and the rollback macro is ready if "
             "the disengagement rate spikes. Priya"),
    "c1m4": (LENA, RAJ, "RE: Drive Assist 3.0 - canary go/no-go", "2025-11-25 17:40",
             "Thanks both. Leadership approved the 1% canary for Monday. Hold the 10% ring "
             "until we have 48 hours of clean telemetry. Lena"),

    # Conversation 2 — perception sign-off (the thread carries a unique PDF)
    "c2m1": (TOMAS, SOFIA, "Perception rc3 evaluation", "2025-11-18 11:00",
             "Sharing the perception rc3 evaluation. Night and rain recall both clear the "
             "3.0 bar. Tomas"),
    "c2m2": (SOFIA, TOMAS, "RE: Perception rc3 evaluation", "2025-11-19 10:20",
             "Reviewed - the long-tail pedestrian cases look good. One note on the "
             "construction-zone scenario in section 4. Sofia"),
    "c2m3": (TOMAS, SOFIA, "RE: Perception rc3 evaluation", "2025-11-20 14:05",
             "Updated the eval with the construction-zone fix and attaching the final "
             "signed evaluation. Tomas"),

    # Conversation 3 — rollout runbook (a forward carries a unique PDF)
    "c3m1": (RAJ, LENA, "Drive Assist 3.0 - staged rollout runbook", "2025-12-01 09:30",
             "Runbook for the staged rollout attached. The auto-halt trips if the canary "
             "disengagement rate regresses beyond the beta baseline. Raj"),
    "c3m2": (PRIYA, LENA, "RE: Drive Assist 3.0 - staged rollout runbook", "2025-12-01 13:00",
             "Comms is ready with the launch-day story and a holding statement if press "
             "picks it up early. Priya"),
    "c3m3": (LENA, RAJ, "RE: Drive Assist 3.0 - staged rollout runbook", "2025-12-02 08:45",
             "Approved. We go 1 percent, 10 percent, 50 percent, 100 percent, each ring "
             "gated on live safety telemetry. Lena"),

    # Conversation 4 — beta incident triage
    "c4m1": (NORA, TOMAS, "Beta incident - elevated handback on left turns", "2026-01-08 22:10",
             "Beta cluster saw an elevated handback rate on unprotected left turns last "
             "night. Pulling the traces now. Nora"),
    "c4m2": (TOMAS, NORA, "RE: Beta incident - elevated handback on left turns", "2026-01-09 09:50",
             "Root-caused to the new lane-change policy interacting with the turn planner. "
             "Hotfix candidate is ready. Tomas"),
    "c4m3": (LENA, TOMAS, "RE: Beta incident - elevated handback on left turns", "2026-01-09 16:30",
             "Good work. Land the hotfix in the next beta build and add a regression "
             "scenario before we resume the rollout. Lena"),
}


def _rfc_date(date, tz):
    """A valid RFC 5322 Date header from 'YYYY-MM-DD HH:MM' + a '+HHMM' offset.
    (Identity ignores the timestamp; this is for display and realism only.)"""
    dt = datetime.strptime(date, "%Y-%m-%d %H:%M")
    sign = 1 if tz[0] != "-" else -1
    off = timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5]))
    return email.utils.format_datetime(dt.replace(tzinfo=timezone(sign * off)))


def _txt_block(key, attachments=None):
    sender, recipient, subject, date, body = M[key]
    lines = ["From: %s" % sender, "Sent: %s" % date,
             "To: %s" % recipient, "Subject: %s" % subject]
    if attachments:
        lines.append("Attachments: %s" % ", ".join(attachments))
    lines += ["", body, ""]
    return "\n".join(lines)


def write_txt(name, keys, attachments_by_key=None):
    """Write a stacked .txt export (newest message first)."""
    attachments_by_key = attachments_by_key or {}
    blocks = [_txt_block(k, attachments_by_key.get(k)) for k in reversed(keys)]
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(blocks).rstrip() + "\n")


def _eml_message(key, attachments=None, tz="-0800"):
    """One EmailMessage for a single canonical message (real .eml = one message)."""
    sender, recipient, subject, date, body = M[key]
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Date"] = _rfc_date(date, tz)
    msg["Message-ID"] = "<%s@voltera.example>" % key
    msg.set_content(body + "\n")
    for att in attachments or []:
        msg.add_attachment(_minimal_pdf(att), maintype="application",
                           subtype="pdf", filename=att)
    return msg


def write_eml(name, key, attachments=None, tz="-0800"):
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(bytes(_eml_message(key, attachments=attachments, tz=tz)))


def write_mbox(name, keys, attachments_by_key=None, tz="-0800"):
    """Write several messages into one .mbox archive (multi-message container)."""
    attachments_by_key = attachments_by_key or {}
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        os.remove(path)
    box = mailbox.mbox(path)
    box.lock()
    try:
        for k in keys:
            box.add(_eml_message(k, attachments=attachments_by_key.get(k), tz=tz))
    finally:
        box.flush()
        box.unlock()
        box.close()


def write_pdf(name):
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(_minimal_pdf(name))


def main():
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            if f != "README.md":
                os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)

    PERCEPTION_PDF = "perception_eval_signed.pdf"
    RUNBOOK_PDF = "rollout_runbook_v3.pdf"

    # Conversation 1 — canary go/no-go: a .txt branch, with cross-format subsets.
    write_txt("a1_canary_full.txt", ["c1m1", "c1m2", "c1m3", "c1m4"])      # KEEP
    write_eml("a1_canary_open.eml", "c1m1")                                # subset -> DELETE
    write_txt("a1_canary_mid.txt", ["c1m2", "c1m3"])                       # subset -> DELETE

    # Conversation 2 — perception sign-off: the .mbox carries the unique PDF.
    write_mbox("a2_perception_thread.mbox", ["c2m1", "c2m2", "c2m3"],
               attachments_by_key={"c2m3": [PERCEPTION_PDF]})             # KEEP
    write_txt("a2_perception_plain.txt", ["c2m1", "c2m2", "c2m3"])         # subset (no att) -> DELETE
    write_eml("a2_perception_early.eml", "c2m1")                           # subset -> DELETE

    # Conversation 3 — rollout runbook: a .txt discussion + a forwarded PDF.
    write_txt("a3_rollout_thread.txt", ["c3m1", "c3m2", "c3m3"])           # KEEP (discussion)
    write_eml("a3_rollout_runbook.eml", "c3m1", attachments=[RUNBOOK_PDF]) # unique att -> KEEP
    write_txt("a3_rollout_open.txt", ["c3m3"])                             # subset -> DELETE

    # Conversation 4 — beta incident: an .mbox that is a timezone-shifted dup.
    write_txt("a4_incident_full.txt", ["c4m1", "c4m2", "c4m3"])            # KEEP
    write_mbox("a4_incident_tzdup.mbox", ["c4m1", "c4m2", "c4m3"], tz="+0900")  # tz dup -> DELETE
    write_eml("a4_incident_open.eml", "c4m1")                              # subset -> DELETE

    # The PDF attachments, saved right next to the threads.
    write_pdf(PERCEPTION_PDF)
    write_pdf(RUNBOOK_PDF)

    files = [f for f in sorted(os.listdir(OUT)) if f != "README.md"]
    print("Wrote %d file(s) to %s" % (len(files), OUT))
    for f in files:
        print("  " + f)


if __name__ == "__main__":
    main()
