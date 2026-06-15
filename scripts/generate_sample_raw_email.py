"""Emit synthetic .eml / .mbox fixtures into examples/raw_email/.

Uses the standard-library email/mailbox modules to produce valid messages —
including an RFC 2047-encoded (non-ASCII) subject, a file attachment, and an
HTML-only body — so the real-format ingestion path has realistic inputs to read.
Fully synthetic Voltera EV data; no real people, companies, or files.

Run:  python scripts/generate_sample_raw_email.py
"""
import datetime
import email.policy
import email.utils
import mailbox
import os
from email.message import EmailMessage


def _dt(y, mo, d, h, mi):
    return datetime.datetime(y, mo, d, h, mi, tzinfo=datetime.timezone(datetime.timedelta(hours=-8)))


def make(frm, to, when, subject, body, html=None, attachment=None,
         message_id=None, in_reply_to=None, references=None):
    msg = EmailMessage(policy=email.policy.default)
    msg["From"] = frm
    msg["To"] = to
    msg["Date"] = email.utils.format_datetime(when)
    msg["Subject"] = subject
    if message_id is not None:
        msg["Message-ID"] = message_id
    if in_reply_to is not None:
        msg["In-Reply-To"] = in_reply_to
    if references is not None:
        msg["References"] = " ".join(references)
    msg.set_content(body)
    if html is not None:
        msg.add_alternative(html, subtype="html")
    if attachment is not None:
        name, text = attachment
        msg.add_attachment(text.encode("utf-8"), maintype="application", subtype="octet-stream", filename=name)
    return msg


# Single .eml files
EMLS = [
    # 01 and 02 form one real reply chain (02 In-Reply-To 01), so `arc tree`
    # rebuilds them as a two-message conversation from the threading headers.
    ("01_canary_go_no_go.eml", make(
        "Lena Ortiz <lena.ortiz@voltera.example>",
        "Raj Patel <raj.patel@voltera.example>",
        _dt(2025, 11, 24, 9, 0),
        "Drive Assist 3.0 - canary go/no-go",
        "Raj, are we go for the 1% canary next week? I need perception rc3 and the "
        "safety case both signed off before I brief leadership. Lena",
        message_id="<canary-open@voltera.example>",
    )),
    # Non-ASCII subject (forces RFC 2047 encoding) + a file attachment.
    ("02_runbook_attached.eml", make(
        "Raj Patel <raj.patel@voltera.example>",
        "Lena Ortiz <lena.ortiz@voltera.example>",
        _dt(2025, 11, 26, 16, 45),
        "RE: Drive Assist 3.0 — canary go/no-go ✅",
        "Runbook attached. The auto-halt trips if the canary disengagement rate "
        "regresses beyond the beta baseline. Raj",
        attachment=("rollout_runbook.pdf", "ROLLOUT RUNBOOK\n1. 1% canary\n2. 10% ring\n..."),
        message_id="<canary-runbook@voltera.example>",
        in_reply_to="<canary-open@voltera.example>",
        references=["<canary-open@voltera.example>"],
    )),
    # HTML-only body (must be flattened to text on ingest). A separate thread.
    ("03_perception_signoff.eml", make(
        "Tomás Vidal <tomas.vidal@voltera.example>",
        "Aisha Bello <aisha.bello@voltera.example>",
        _dt(2025, 7, 8, 11, 30),
        "Perception sign-off (rc3)",
        "Validation accepts rc3. Perception is signed off for the beta program.",
        html="<html><body><p>Validation accepts <b>rc3</b>. "
             "Perception is <i>signed off</i> for the beta program.</p></body></html>",
        message_id="<perception-rc3@voltera.example>",
    )),
]

# A small .mbox archive (several messages in one file).
MBOX_MSGS = [
    make("Dev Anand <dev.anand@voltera.example>", "Raj Patel <raj.patel@voltera.example>",
         _dt(2025, 5, 6, 15, 40), "Rollback drill results",
         "Game-day done. Full-fleet rollback completed in 22 minutes end to end. Dev",
         message_id="<rollback-drill@voltera.example>"),
    make("Aisha Bello <aisha.bello@voltera.example>", "Dana Olsen <dana.olsen@voltera.example>",
         _dt(2025, 9, 19, 11, 15), "Safety case approved",
         "Safety leadership has approved the case for staged rollout. Aisha",
         attachment=("safety_case_final.pdf", "SAFETY CASE v3 - approved"),
         message_id="<safety-approved@voltera.example>"),
    make("Marco Ruiz <marco.ruiz@voltera.example>", "Program <program@voltera.example>",
         _dt(2025, 12, 1, 8, 5), "1% canary live",
         "First production ring received Drive Assist 3.0. Canary metrics matched beta. Marco",
         message_id="<canary-live@voltera.example>"),
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.normpath(os.path.join(here, "..", "examples", "raw_email"))
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        if name.endswith((".eml", ".mbox")):
            os.remove(os.path.join(out_dir, name))

    for name, msg in EMLS:
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(msg.as_bytes())

    mbox_path = os.path.join(out_dir, "team.mbox")
    box = mailbox.mbox(mbox_path)
    box.lock()
    try:
        for msg in MBOX_MSGS:
            box.add(mailbox.mboxMessage(msg.as_bytes()))
        box.flush()
    finally:
        box.unlock()
        box.close()

    print("Wrote %d .eml + 1 .mbox (%d messages) to %s"
          % (len(EMLS), len(MBOX_MSGS), out_dir))


if __name__ == "__main__":
    main()
