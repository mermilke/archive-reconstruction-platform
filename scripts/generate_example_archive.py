#!/usr/bin/env python3
"""Generate examples/archive/ — a large, realistic, mixed-format export pile.

Where examples/threads/ is the minimal teaching fixture (six .txt files, the
canonical "keep 2, delete 4" case the tests pin), examples/archive/ is the
*messy real-world pile* you actually get after archiving a mailbox: a dozen
conversations, each exported several times over, in different formats, with the
PDF attachments saved right alongside the threads.

It exercises everything the dedup core handles:

* three input formats in one folder — ``.txt`` stacked exports, real ``.eml``
  messages, and ``.mbox`` archives — deduped together;
* cross-format redundancy — single-message ``.eml`` files that are subsets of a
  ``.txt``/``.mbox`` thread, and ``.mbox`` exports that are timezone-shifted
  subsets (collapsed, because timestamps are deliberately ignored);
* attachment-driven keeps — a forwarded ``.eml`` (or an ``.mbox`` thread) whose
  only unique content is a PDF is never marked redundant (the crown jewel);
* PDFs as first-class attachments — the real ``.pdf`` files sit in the folder
  too. The dedup engine reads ``.txt``/``.eml``/``.mbox`` (stdlib only, zero
  dependencies) and treats each attachment by *name*; the PDFs are never parsed
  as inputs, they ride along as attachments.

The corpus is generated from a declarative spec below, so each file's role
(branch to keep vs. redundant subset) is explicit and the dedup verdict is
deterministic. Filenames encode the role — ``*_full`` / ``*_thread`` /
``*_forward`` are branches to keep; ``*_early`` / ``*_mid`` / ``*_open`` /
``*_plain`` / ``*_tzdup`` are redundant subsets. tests/test_archive_example.py
relies on that convention.

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
KENJI = "Kenji Watanabe <kenji.watanabe@voltera.example>"
MARA = "Mara Lindqvist <mara.lindqvist@voltera.example>"
OMAR = "Omar Haddad <omar.haddad@voltera.example>"
IVY = "Ivy Chen <ivy.chen@voltera.example>"

# Each conversation: slug, subject, who the opener writes to, base date, the
# "kind" (forward = a forwarded .eml carries a unique PDF; thread = the thread
# itself carries the PDF; plain = no attachment), the format of the kept thread,
# the attachment name (if any), and the messages [(sender, body)].
CONVERSATIONS = [
    dict(slug="c01_perception", subject="Perception rc3 evaluation", to=SOFIA,
         base="2025-11-18 09:00", kind="forward", fmt="txt",
         attachment="c01_perception_eval.pdf", msgs=[
             (TOMAS, "Sharing the perception rc3 evaluation; night and rain recall both clear the 3.0 bar. Tomas"),
             (SOFIA, "Reviewed - the long-tail pedestrian cases look good, one note on the construction-zone scenario in section 4. Sofia"),
             (TOMAS, "Pushed the construction-zone fix and re-ran the eval overnight; the numbers held. Tomas"),
             (SOFIA, "Signed off. Attaching the final evaluation for the record. Sofia")]),

    dict(slug="c02_canary", subject="Drive Assist 3.0 - canary go/no-go", to=RAJ,
         base="2025-11-24 09:00", kind="thread", fmt="mbox",
         attachment="c02_canary_brief.pdf", msgs=[
             (LENA, "Are we go for the 1% canary next week? I need perception and the safety case both signed before I brief leadership. Lena"),
             (RAJ, "Perception rc3 is signed and the release candidate build is cut; from engineering we are go. Raj"),
             (PRIYA, "Support is staffed for the canary window and the rollback macro is ready if disengagement spikes. Priya"),
             (LENA, "Leadership approved the 1% canary for Monday; the briefing deck is attached. Lena")]),

    dict(slug="c03_runbook", subject="Drive Assist 3.0 - staged rollout runbook", to=LENA,
         base="2025-12-01 09:00", kind="forward", fmt="txt",
         attachment="c03_runbook_v3.pdf", msgs=[
             (RAJ, "Drafted the staged rollout runbook; the auto-halt trips if disengagement regresses past the beta baseline. Raj"),
             (PRIYA, "Comms is ready with a launch-day story and a holding statement if press picks it up early. Priya"),
             (LENA, "Approved the ring plan: 1, 10, 50, 100 percent, each gated on live safety telemetry. Lena"),
             (RAJ, "Final runbook attached with the gating thresholds baked in. Raj")]),

    dict(slug="c04_incident", subject="Beta incident - elevated handback on left turns", to=TOMAS,
         base="2026-01-08 22:00", kind="plain", fmt="mbox", attachment=None, msgs=[
             (NORA, "Beta cluster saw an elevated handback rate on unprotected left turns last night; pulling the traces. Nora"),
             (TOMAS, "Root-caused to the lane-change policy interacting with the turn planner; a hotfix candidate is ready. Tomas"),
             (LENA, "Land the hotfix in the next beta build and add a regression scenario before we resume the rollout. Lena"),
             (NORA, "Hotfix verified on the replay set; the handback rate is back to baseline. Nora")]),

    dict(slug="c05_localization", subject="Localization handoff - 14 launch markets", to=MARA,
         base="2025-12-10 10:00", kind="forward", fmt="txt",
         attachment="c05_loc_kit.pdf", msgs=[
             (SOFIA, "Strings and voice cues are frozen for the 14 launch markets and ready for localization. Sofia"),
             (MARA, "Received - flagging two cues that don't fit the German UI width. Mara"),
             (SOFIA, "Shortened both cues and updated the source strings. Sofia"),
             (MARA, "Localized kit attached; all 14 markets pass the length checks. Mara")]),

    dict(slug="c06_telemetry", subject="Telemetry pipeline for canary gating", to=RAJ,
         base="2025-11-12 11:00", kind="thread", fmt="mbox",
         attachment="c06_pipeline_spec.pdf", msgs=[
             (MARA, "The telemetry pipeline now ingests canary disengagement events within two minutes end to end. Mara"),
             (RAJ, "Good; make sure the auto-halt query reads from the low-latency view. Raj"),
             (MARA, "Switched the query and load-tested at ten times canary volume. Mara"),
             (RAJ, "Approved; the pipeline spec is attached for the on-call runbook. Raj")]),

    dict(slug="c07_app", subject="Companion app - trip review screen", to=LENA,
         base="2025-12-15 13:00", kind="forward", fmt="txt",
         attachment="c07_app_review.pdf", msgs=[
             (OMAR, "The companion app's trip-review screen is ready for design review. Omar"),
             (LENA, "Looks strong; make the hand-back moments easier to scan at a glance. Lena"),
             (OMAR, "Reworked the timeline view so hand-backs stand out. Omar"),
             (OMAR, "Review build attached with the updated trip-review screen. Omar")]),

    dict(slug="c08_support", subject="Support readiness for the rollout wave", to=LENA,
         base="2025-12-18 09:00", kind="plain", fmt="mbox", attachment=None, msgs=[
             (PRIYA, "Drafted the support staffing and tooling plan for the rollout wave. Priya"),
             (LENA, "Add a dedicated queue for disengagement reports during the canary. Lena"),
             (PRIYA, "Added the queue and a macro that pulls the relevant trip id. Priya"),
             (PRIYA, "Support readiness is green for Monday. Priya")]),

    dict(slug="c09_regulatory", subject="Market applicability matrix", to=LENA,
         base="2025-11-28 10:00", kind="forward", fmt="txt",
         attachment="c09_reg_matrix.pdf", msgs=[
             (KENJI, "Mapped which assist behaviors are permitted in each launch market. Kenji"),
             (LENA, "Flag any market where the lane-change behavior needs to ship disabled. Lena"),
             (KENJI, "Two markets require it off at launch; noted in the matrix. Kenji"),
             (KENJI, "Applicability matrix attached, final for launch. Kenji")]),

    dict(slug="c10_comms", subject="Launch-day blog and press statement", to=PRIYA,
         base="2026-01-20 09:00", kind="plain", fmt="mbox", attachment=None, msgs=[
             (IVY, "Drafted the launch-day blog post and the reactive press statement. Ivy"),
             (PRIYA, "Tighten the safety framing and lead with the staged rollout. Priya"),
             (IVY, "Reframed around the staged rollout and the safety telemetry gates. Ivy"),
             (IVY, "Final copy locked for launch day. Ivy")]),
]

# Build the canonical message table: each logical message defined once, reused
# wherever it appears, so the same message has a byte-identical body everywhere.
#   key "<slug>_m<i>" -> (sender, recipient, subject, "YYYY-MM-DD HH:MM", body)
M = {}
for _conv in CONVERSATIONS:
    _base = datetime.strptime(_conv["base"], "%Y-%m-%d %H:%M")
    _prev = _conv["to"]
    for _i, (_sender, _body) in enumerate(_conv["msgs"]):
        _subj = _conv["subject"] if _i == 0 else "RE: " + _conv["subject"]
        _date = (_base + timedelta(days=_i, hours=_i)).strftime("%Y-%m-%d %H:%M")
        _recip = _conv["to"] if _i == 0 else _prev
        M["%s_m%d" % (_conv["slug"], _i)] = (_sender, _recip, _subj, _date, _body)
        _prev = _sender


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


def write_txt(name, keys, attachment_on_last=None):
    """Write a stacked .txt export (newest message first)."""
    atts = {keys[-1]: [attachment_on_last]} if attachment_on_last else {}
    blocks = [_txt_block(k, atts.get(k)) for k in reversed(keys)]
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(blocks).rstrip() + "\n")


def write_eml(name, key, attachments=None, tz="-0800"):
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(bytes(_eml_message(key, attachments=attachments, tz=tz)))


def write_mbox(name, keys, attachment_on_last=None, tz="-0800"):
    """Write several messages into one .mbox archive (multi-message container)."""
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        os.remove(path)
    box = mailbox.mbox(path)
    box.lock()
    try:
        for i, k in enumerate(keys):
            atts = [attachment_on_last] if (attachment_on_last and i == len(keys) - 1) else None
            box.add(_eml_message(k, attachments=atts, tz=tz))
    finally:
        box.flush()
        box.unlock()
        box.close()


def write_pdf(name):
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(_minimal_pdf(name))


def _write_thread(name, fmt, keys, attachment_on_last=None, tz="-0800"):
    if fmt == "mbox":
        write_mbox(name, keys, attachment_on_last=attachment_on_last, tz=tz)
    else:
        write_txt(name, keys, attachment_on_last=attachment_on_last)


def main():
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            if f != "README.md":
                os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)

    pdfs = set()
    for conv in CONVERSATIONS:
        slug, fmt, att = conv["slug"], conv["fmt"], conv["attachment"]
        n = len(conv["msgs"])
        keys = ["%s_m%d" % (slug, i) for i in range(n)]
        ext = "mbox" if fmt == "mbox" else "txt"

        # --- the branch(es) to KEEP ---
        if conv["kind"] == "thread":          # the thread itself carries the PDF
            _write_thread("%s_thread.%s" % (slug, ext), fmt, keys, attachment_on_last=att)
            write_txt("%s_plain.txt" % slug, keys)                 # same messages, no PDF -> subset
            pdfs.add(att)
        else:                                  # forward / plain: a no-attachment thread
            _write_thread("%s_full.%s" % (slug, ext), fmt, keys)
        if conv["kind"] == "forward":          # a forwarded single message carrying the PDF
            write_eml("%s_forward.eml" % slug, keys[-1], attachments=[att])
            pdfs.add(att)

        # --- redundant SUBSETS, spread across formats ---
        write_txt("%s_early.txt" % slug, keys[0:2])                # first two messages
        write_txt("%s_mid.txt" % slug, keys[1:3])                  # middle two messages
        write_eml("%s_open.eml" % slug, keys[0])                   # single-message .eml subset
        write_mbox("%s_tzdup.mbox" % slug, keys[:-1], tz="+0900")  # tz-shifted proper subset

    for nm in sorted(pdfs):
        write_pdf(nm)

    files = [f for f in sorted(os.listdir(OUT)) if f != "README.md"]
    exts = {}
    for f in files:
        e = os.path.splitext(f)[1].lower()
        exts[e] = exts.get(e, 0) + 1
    print("Wrote %d file(s) to %s" % (len(files), OUT))
    print("  by type: " + ", ".join("%s:%d" % (k, v) for k, v in sorted(exts.items())))


if __name__ == "__main__":
    main()
