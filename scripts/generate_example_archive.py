#!/usr/bin/env python3
"""Generate examples/archive/ — a large, realistic, mixed-format export pile.

Where examples/threads/ is the minimal teaching fixture (six .txt files, the
canonical "keep 2, delete 4" case the tests pin), examples/archive/ is the
*messy real-world pile* you actually get after archiving a mailbox: many
conversations, each exported several times over, in different formats, with the
attachments saved right alongside the threads.

It exercises everything the dedup core handles, including the tricky cases:

* three input formats in one folder — ``.txt`` stacked exports, real ``.eml``
  messages, and ``.mbox`` archives — deduped together;
* cross-format redundancy — single-message ``.eml`` files that are subsets of a
  ``.txt``/``.mbox`` thread, and ``.mbox`` exports that are timezone-shifted
  subsets (collapsed, because timestamps are deliberately ignored);
* normalization collapse — the same message re-exported with a quoted-reply
  tail, a ``-- `` signature, or as an HTML-only body all fold back onto the
  plain original (only the identity fingerprint is cleaned; display text is
  untouched);
* a three-way branch — three exports where *none* is a subset of the others
  (each holds a reply the others lack), so all three are kept: the clearest
  proof that "biggest file" is the wrong heuristic;
* attachment branching — two files that share their messages but carry
  *different* attachments are both kept; attachments come in several types
  (``.pdf``/``.csv``/``.png``), matched by name;
* a large multi-message ``.mbox`` (a Takeout-style digest) kept as its own
  branch;
* emails saved/printed to PDF, read as inputs by the best-effort PDF reader —
  saved-to-PDF excerpts of a thread fold in as cross-format subsets, and a
  conversation that exists *only* as a PDF is read and kept as a branch. (A PDF
  named as another message's *attachment* still stays an attachment — the two
  kinds of PDF coexist in this one folder.)

The corpus is generated from a declarative spec, so each file's role is explicit
and the dedup verdict is deterministic. Filenames encode the role — branches to
KEEP are ``*_full`` / ``*_thread`` / ``*_forward`` / ``*_branch[abc]`` /
``*_att[ab]``; redundant subsets are ``*_early`` / ``*_mid`` / ``*_open`` /
``*_plain`` / ``*_tzdup`` / ``*_quoted`` / ``*_sig`` / ``*_html``.
tests/test_archive_example.py relies on that convention.

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
from generate_sample_events import _PNG_1x1, _minimal_pdf  # noqa: E402

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

# Standard conversations (slug, subject, opener's recipient, base date, kind,
# kept-thread format, attachment name, messages). kind: forward = a forwarded
# .eml carries a unique PDF; thread = the thread itself carries the PDF; plain =
# no attachment.
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

# Special conversations for the tricky cases — written by hand-rolled logic in
# main() rather than the standard pattern.
SPECIAL = [
    dict(slug="c11_threeway", subject="Auto lane-change design review", to=RAJ,
         base="2025-12-05 09:00", msgs=[
             (LENA, "Kicking off the auto lane-change design review for Drive Assist 3.0. Lena"),
             (RAJ, "Baseline behavior looks solid; the open question is how aggressive to tune gap acceptance. Raj"),
             (SOFIA, "From perception, the side-detection margin supports a slightly tighter gap. Sofia"),
             (KENJI, "From regulatory, two markets cap lane-change assertiveness, so we need a regional profile. Kenji"),
             (NORA, "From validation, the tighter gap needs three new scenarios before we ship. Nora")]),

    dict(slug="c12_normalize", subject="rc3 metrics - go/no-go", to=SOFIA,
         base="2025-11-21 09:00", msgs=[
             (TOMAS, "Posting the rc3 metrics summary for the go/no-go thread. Tomas"),
             (SOFIA, "Numbers look good to me. Sofia"),
             (LENA, "Approved on my side; let us proceed to the canary. Lena")]),

    dict(slug="c13_assets", subject="Trip-review design assets", to=LENA,
         base="2025-12-16 09:00", msgs=[
             (OMAR, "Design assets for the trip-review screen are ready; sharing the spec variants and metrics. Omar"),
             (LENA, "Thanks; please keep both the v1 and v2 spec variants on file. Lena")]),

    dict(slug="c14_mailbox", subject="Drive Assist 3.0 weekly digest", to=RAJ,
         base="2026-01-15 08:00", msgs=[
             (IVY, "Weekly Drive Assist 3.0 digest: canary metrics, incidents, and rollout status. Ivy"),
             (RAJ, "Engineering: rc3 shipped, two minor hotfixes queued. Raj"),
             (NORA, "Validation: scenario suite at 94 percent pass, three flaky cases under review. Nora"),
             (PRIYA, "Support: ticket volume nominal, one macro updated this week. Priya"),
             (MARA, "Cloud: telemetry latency p95 is under ninety seconds. Mara"),
             (KENJI, "Regulatory: two markets confirmed for the limited launch profile. Kenji")]),

    dict(slug="c15_pdfsaved", subject="Drive Assist 3.0 exec summary", to=LENA,
         base="2026-01-22 09:00", msgs=[
             (LENA, "Pulling the Drive Assist 3.0 exec summary together for the board read-out. Lena"),
             (RAJ, "Engineering section is accurate: rc3 shipped and the canary held at target. Raj"),
             (LENA, "Final exec summary locked; saving a PDF for the board packet. Lena")]),

    dict(slug="c16_pdfonly", subject="Pre-launch legal sign-off", to=KENJI,
         base="2026-01-26 10:00", msgs=[
             (KENJI, "Legal has cleared the launch disclosures for all but the two restricted markets. Kenji"),
             (LENA, "Noted; ship those two markets with the lane-change assist disabled at launch. Lena")]),
]

# Build the canonical message table: each logical message defined once, reused
# wherever it appears, so the same message has a byte-identical body everywhere.
#   key "<slug>_m<i>" -> (sender, recipient, subject, "YYYY-MM-DD HH:MM", body)
M = {}
for _conv in CONVERSATIONS + SPECIAL:
    _base = datetime.strptime(_conv["base"], "%Y-%m-%d %H:%M")
    _prev = _conv["to"]
    for _i, (_sender, _body) in enumerate(_conv["msgs"]):
        _subj = _conv["subject"] if _i == 0 else "RE: " + _conv["subject"]
        _date = (_base + timedelta(days=_i, hours=_i)).strftime("%Y-%m-%d %H:%M")
        _recip = _conv["to"] if _i == 0 else _prev
        M["%s_m%d" % (_conv["slug"], _i)] = (_sender, _recip, _subj, _date, _body)
        _prev = _sender

# Real bytes per attachment type, so the files in the folder match their
# extension (a .png stub named .png, readable CSV, a one-page PDF).
_MIME = {"pdf": ("application", "pdf"), "png": ("image", "png"), "csv": ("text", "csv")}


def _ext(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _attachment_bytes(name):
    ext = _ext(name)
    if ext == "png":
        return _PNG_1x1
    if ext == "csv":
        return ("file,note\r\n%s,synthetic sample attachment\r\n" % name).encode("utf-8")
    return _minimal_pdf(name)


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


def _eml_message(key, attachments=None, tz="-0800", body=None, html=False):
    """One EmailMessage for a single canonical message (real .eml = one message).

    ``body`` overrides the message text (used to append a quote tail / signature);
    ``html`` emits an HTML-only body. Either path still fingerprints back to the
    canonical message once normalization runs."""
    sender, recipient, subject, date, canon = M[key]
    text = (canon + "\n") if body is None else body
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Date"] = _rfc_date(date, tz)
    msg["Message-ID"] = "<%s@voltera.example>" % key
    if html:
        msg.set_content(text, subtype="html")
    else:
        msg.set_content(text)
    for att in attachments or []:
        maintype, subtype = _MIME.get(_ext(att), ("application", "octet-stream"))
        msg.add_attachment(_attachment_bytes(att), maintype=maintype,
                           subtype=subtype, filename=att)
    return msg


def write_txt(name, keys, attachments_on_last=None):
    """Write a stacked .txt export (newest message first)."""
    atts = {keys[-1]: attachments_on_last} if attachments_on_last else {}
    blocks = [_txt_block(k, atts.get(k)) for k in reversed(keys)]
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(blocks).rstrip() + "\n")


def write_eml(name, key, attachments=None, tz="-0800", body=None, html=False):
    msg = _eml_message(key, attachments=attachments, tz=tz, body=body, html=html)
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(bytes(msg))


def write_mbox(name, keys, attachments_on_last=None, tz="-0800"):
    """Write several messages into one .mbox archive (multi-message container)."""
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        os.remove(path)
    box = mailbox.mbox(path)
    box.lock()
    try:
        for i, k in enumerate(keys):
            atts = attachments_on_last if (attachments_on_last and i == len(keys) - 1) else None
            box.add(_eml_message(k, attachments=atts, tz=tz))
    finally:
        box.flush()
        box.unlock()
        box.close()


def write_pdf(name):
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(_attachment_bytes(name))


def _email_pdf_bytes(lines):
    """A one-page PDF whose selectable text is ``lines`` (one per source line).

    Unlike the attachment stubs from :func:`_minimal_pdf`, this renders a full
    exported-email block, so the stdlib PDF reader recovers 'From:/Sent:/Subject:'
    and the file parses back into the same Message a .txt export would — i.e. an
    email genuinely *saved/printed to PDF*, read as an input and deduped."""
    ops = ["BT", "/F1 11 Tf", "72 730 Td"]
    for i, ln in enumerate(lines):
        if i:
            ops.append("0 -14 Td")
        esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append("(%s) Tj" % esc)
    ops.append("ET")
    stream = " ".join(ops).encode("latin-1", "replace")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objs) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % n
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (n, xref_pos)
    return bytes(out)


def write_email_pdf(name, keys):
    """Write several canonical messages as one exported-email PDF (read as input)."""
    lines = []
    for k in reversed(keys):  # newest-first, like the .txt exports
        lines += _txt_block(k).split("\n")
    with open(os.path.join(OUT, name), "wb") as fh:
        fh.write(_email_pdf_bytes(lines))


def _write_thread(name, fmt, keys, attachments_on_last=None, tz="-0800"):
    if fmt == "mbox":
        write_mbox(name, keys, attachments_on_last=attachments_on_last, tz=tz)
    else:
        write_txt(name, keys, attachments_on_last=attachments_on_last)


def _keys(slug, n):
    return ["%s_m%d" % (slug, i) for i in range(n)]


def main():
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            if f != "README.md":
                os.remove(os.path.join(OUT, f))
    os.makedirs(OUT, exist_ok=True)

    attachments = set()

    # --- Standard conversations (c01-c10): a branch + cross-format subsets ---
    for conv in CONVERSATIONS:
        slug, fmt, att = conv["slug"], conv["fmt"], conv["attachment"]
        keys = _keys(slug, len(conv["msgs"]))
        ext = "mbox" if fmt == "mbox" else "txt"

        if conv["kind"] == "thread":          # the thread itself carries the PDF
            _write_thread("%s_thread.%s" % (slug, ext), fmt, keys, attachments_on_last=[att])
            write_txt("%s_plain.txt" % slug, keys)                 # same messages, no PDF -> subset
            attachments.add(att)
        else:                                  # forward / plain: a no-attachment thread
            _write_thread("%s_full.%s" % (slug, ext), fmt, keys)
        if conv["kind"] == "forward":          # a forwarded single message carrying the PDF
            write_eml("%s_forward.eml" % slug, keys[-1], attachments=[att])
            attachments.add(att)

        write_txt("%s_early.txt" % slug, keys[0:2])                # first two messages
        write_txt("%s_mid.txt" % slug, keys[1:3])                  # middle two messages
        write_eml("%s_open.eml" % slug, keys[0])                   # single-message .eml subset
        write_mbox("%s_tzdup.mbox" % slug, keys[:-1], tz="+0900")  # tz-shifted proper subset

    # --- c11: a three-way branch (none is a subset of the others) ---
    k = _keys("c11_threeway", 5)
    write_txt("c11_threeway_brancha.txt", [k[0], k[1], k[2]])      # KEEP
    write_mbox("c11_threeway_branchb.mbox", [k[0], k[1], k[3]])    # KEEP
    write_txt("c11_threeway_branchc.txt", [k[0], k[1], k[4]])      # KEEP
    write_eml("c11_threeway_open.eml", k[0])                       # subset -> DELETE
    write_txt("c11_threeway_early.txt", [k[0], k[1]])              # subset -> DELETE

    # --- c12: normalization collapse (quote tail / signature / HTML-only) ---
    k = _keys("c12_normalize", 3)
    write_txt("c12_normalize_full.txt", k)                         # KEEP
    quote_tail = (M[k[2]][4] + "\n\nOn Fri, 21 Nov 2025 09:00:00 -0800, "
                  + "Sofia Marenko <sofia.marenko@voltera.example> wrote:\n> "
                  + M[k[1]][4] + "\n")
    write_eml("c12_normalize_quoted.eml", k[2], body=quote_tail)   # quote stripped -> subset
    sig_body = M[k[1]][4] + "\n\n-- \nSofia Marenko\nPerception Lead, Voltera\n"
    write_eml("c12_normalize_sig.eml", k[1], body=sig_body)        # signature stripped -> subset
    html_body = "<html><body><p>%s</p></body></html>" % M[k[0]][4]
    write_eml("c12_normalize_html.eml", k[0], body=html_body, html=True)  # HTML->text -> subset

    # --- c13: attachment branching across several attachment types ---
    k = _keys("c13_assets", 2)
    write_txt("c13_assets_atta.txt", k,
              attachments_on_last=["spec_v1.pdf", "ride_metrics.csv"])     # KEEP
    write_eml("c13_assets_attb.eml", k[1],
              attachments=["spec_v2.pdf", "screen_mock.png"])             # KEEP (different atts)
    write_txt("c13_assets_plain.txt", k)                                   # no atts -> subset of atta
    write_eml("c13_assets_forward.eml", k[0], attachments=["launch_budget.csv"])  # unique att -> KEEP
    attachments.update(["spec_v1.pdf", "ride_metrics.csv", "spec_v2.pdf",
                        "screen_mock.png", "launch_budget.csv"])

    # --- c14: a large multi-message .mbox (Takeout-style digest) ---
    k = _keys("c14_mailbox", 6)
    write_mbox("c14_mailbox_full.mbox", k)                         # KEEP (6 unique messages)
    write_eml("c14_mailbox_open.eml", k[0])                        # subset -> DELETE
    write_txt("c14_mailbox_early.txt", [k[0], k[1]])              # subset -> DELETE

    # --- c15: emails saved/printed to PDF, read as inputs and deduped ---
    # The thread also lives as a .txt branch; the saved-to-PDF excerpts are read
    # by the stdlib PDF reader and recognized as cross-format subsets of it.
    k = _keys("c15_pdfsaved", 3)
    write_txt("c15_pdfsaved_full.txt", k)                          # KEEP (full thread)
    write_email_pdf("c15_pdfsaved_open.pdf", [k[0]])              # saved PDF, subset -> DELETE
    write_email_pdf("c15_pdfsaved_early.pdf", [k[0], k[1]])       # saved PDF, subset -> DELETE

    # --- c16: a conversation that exists ONLY as a saved PDF (kept branch) ---
    k = _keys("c16_pdfonly", 2)
    write_email_pdf("c16_pdfonly_full.pdf", k)                     # KEEP (read from PDF, unique)

    for nm in sorted(attachments):
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
