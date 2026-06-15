"""Read real exported email formats (``.eml`` and ``.mbox``) into Message objects.

Standard library only (``email`` + ``mailbox``). Every message is mapped onto the
same :class:`arc.parse.Message` model the rest of the toolkit already uses, so
dedup, timeline, bridge, and organize work on real mailbox exports unchanged.

Gmail, Outlook, Apple Mail, and Thunderbird all export ``.mbox`` and/or ``.eml``,
so this is what turns the toolkit from "works on our text format" into "point it
at your actual mail."
"""
from __future__ import annotations

import email
import email.policy
import email.utils
import html as _html
import mailbox
import re
from typing import List

from .parse import Message

_TAG_RE = re.compile(r"<[^>]+>")
_INLINE_WS_RE = re.compile(r"[ \t\r\f\v]+")


def parse_eml(path: str) -> List[Message]:
    """Parse a single ``.eml`` file (one message) into a one-element list."""
    with open(path, "rb") as fh:
        msg = email.message_from_binary_file(fh, policy=email.policy.default)
    return [_to_message(msg)]


def parse_mbox(path: str) -> List[Message]:
    """Parse every message in an ``.mbox`` archive."""
    box = mailbox.mbox(path)
    out: List[Message] = []
    try:
        for key in box.keys():
            raw = box.get_bytes(key)
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            out.append(_to_message(msg))
    finally:
        box.close()
    return out


def _header(msg, name: str) -> str:
    # With policy.default, header values decode RFC 2047 encoded-words for us.
    value = msg[name]
    return str(value).strip() if value is not None else ""


def _timestamp(msg) -> str:
    value = msg["Date"]
    dt = None
    if value is not None:
        dt = getattr(value, "datetime", None)  # DateHeader under policy.default
        if dt is None:
            try:
                dt = email.utils.parsedate_to_datetime(str(value))
            except (TypeError, ValueError):
                dt = None
    if dt is None:
        return _header(msg, "Date")
    return dt.strftime("%Y-%m-%d %H:%M")


def _html_to_text(value: str) -> str:
    text = _TAG_RE.sub(" ", value or "")
    text = _html.unescape(text)
    lines = [_INLINE_WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def _content(part) -> str:
    try:
        return part.get_content() or ""
    except (LookupError, ValueError, KeyError):
        # Unknown charset / undecodable part — fall back to a best-effort decode.
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload.decode("utf-8", "replace")
        return str(payload or "")


def _body(msg) -> str:
    part = None
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
    except Exception:
        part = None
    if part is not None:
        text = _content(part)
        if part.get_content_type() == "text/html":
            return _html_to_text(text)
        return text.strip()

    # Fallbacks for unusual structures.
    if msg.is_multipart():
        for sub in msg.walk():
            if sub.get_content_type() == "text/plain":
                return _content(sub).strip()
        for sub in msg.walk():
            if sub.get_content_type() == "text/html":
                return _html_to_text(_content(sub))
        return ""
    text = _content(msg)
    if msg.get_content_type() == "text/html":
        return _html_to_text(text)
    return text.strip()


def _attachments(msg) -> List[str]:
    names: List[str] = []
    try:
        for part in msg.iter_attachments():
            filename = part.get_filename()
            if filename:
                names.append(str(filename).strip())
    except Exception:
        pass
    return names


def _references(msg) -> List[str]:
    raw = msg["References"]
    if raw is None:
        return []
    tokens = re.findall(r"<[^>]+>", str(raw))
    if tokens:
        return tokens
    return [t for t in str(raw).split() if t]


def _to_message(msg) -> Message:
    return Message(
        sender=_header(msg, "From"),
        timestamp=_timestamp(msg),
        recipient=_header(msg, "To"),
        subject=_header(msg, "Subject"),
        attachments=_attachments(msg),
        body=_body(msg),
        message_id=_header(msg, "Message-ID"),
        in_reply_to=_header(msg, "In-Reply-To"),
        references=_references(msg),
    )
