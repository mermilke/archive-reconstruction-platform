"""Parse exported email-thread text into :class:`Message` objects.

The expected export format stacks messages **newest-first**. Each message starts
with a header block (``Key: value`` lines), then a blank line, then the body::

    From: Raj Patel <raj.patel@voltera.example>
    Sent: 2025-11-26 16:45
    To: Lena Ortiz <lena.ortiz@voltera.example>
    Subject: RE: Drive Assist 3.0 - canary go/no-go
    Attachments: rollout_runbook.pdf

    Body text here.

Header keys are case-insensitive. ``Sent:`` and ``Date:`` are interchangeable.
Timestamps are captured but the dedup logic deliberately ignores them, because
the same message often renders with different times across exports.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

# Input formats the toolkit can read from a folder.
SUPPORTED_EXTS = (".txt", ".eml", ".mbox")

# A header line is ``Word: value`` where Word may contain hyphens (e.g. Reply-To).
_HEADER_RE = re.compile(r"^([A-Za-z][A-Za-z\-]*):\s*(.*)$")


@dataclass
class Message:
    """A single message extracted from a thread export.

    ``timestamp`` is retained for display but is never used to decide identity.

    ``message_id`` / ``in_reply_to`` / ``references`` carry the RFC 5322 threading
    headers when an export preserves them (real ``.eml``/``.mbox`` always do; the
    plain-text format may). They are what roadmap item 3's thread-tree
    reconstruction uses to rebuild the actual conversation, and to cross-check
    that dedup never drops a unique message. ``references`` is the ordered list of
    referenced message-ids (raw, e.g. ``<id@host>``); normalization happens in
    :mod:`arc.thread`.
    """

    sender: str = ""
    timestamp: str = ""
    recipient: str = ""
    subject: str = ""
    attachments: List[str] = field(default_factory=list)
    body: str = ""
    message_id: str = ""
    in_reply_to: str = ""
    references: List[str] = field(default_factory=list)


def parse_thread(text: str) -> List[Message]:
    """Parse the full text of one export file into a list of messages.

    Messages are returned in the order they appear (newest-first for the
    standard export format). A new message boundary is a ``From:`` header that
    begins a header block — i.e. it sits at the start of the file or directly
    after a blank line.
    """
    lines = text.splitlines()

    starts: List[int] = []
    for i, line in enumerate(lines):
        m = _HEADER_RE.match(line)
        if m and m.group(1).lower() == "from":
            if i == 0 or lines[i - 1].strip() == "":
                starts.append(i)

    if not starts:
        return []

    starts.append(len(lines))
    messages: List[Message] = []
    for start, end in zip(starts, starts[1:]):
        msg = _parse_block(lines[start:end])
        if msg is not None:
            messages.append(msg)
    return messages


def parse_file(path: str) -> List[Message]:
    """Read a stacked thread-export ``.txt`` file and parse it into messages."""
    with open(path, "r", encoding="utf-8") as fh:
        return parse_thread(fh.read())


def parse_path(path: str) -> List[Message]:
    """Parse a file into messages, dispatching by extension.

    ``.eml`` and ``.mbox`` are read with the stdlib email/mailbox modules (one or
    many messages); ``.pdf`` is read best-effort (see :mod:`arc.pdf_in`);
    anything else is treated as the stacked ``.txt`` export.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".eml":
        from .email_in import parse_eml
        return parse_eml(path)
    if ext == ".mbox":
        from .email_in import parse_mbox
        return parse_mbox(path)
    if ext == ".pdf":
        from .pdf_in import parse_pdf
        return parse_pdf(path)
    return parse_file(path)


def find_message_files(directory: str, recursive: bool = False, pattern: Optional[str] = None) -> List[str]:
    """List readable message files under ``directory``.

    With no ``pattern``, gathers every supported extension (``.txt``/``.eml``/
    ``.mbox``); with a ``pattern`` (e.g. ``*.eml``), uses just that glob.
    """
    if pattern:
        root = os.path.join(directory, "**", pattern) if recursive else os.path.join(directory, pattern)
        return sorted(glob.glob(root, recursive=recursive))
    found: List[str] = []
    for ext in SUPPORTED_EXTS:
        root = os.path.join(directory, "**", "*" + ext) if recursive else os.path.join(directory, "*" + ext)
        found.extend(glob.glob(root, recursive=recursive))
    return sorted(set(found))


def _parse_block(block: List[str]) -> Optional[Message]:
    """Parse one message block: header lines, then the body.

    Well-formed blocks separate the two with a blank line. Real exports are not
    always well-formed, so the header scan also stops at the first line that is
    neither a ``Key: value`` header nor a folded continuation of the previous
    header — that line begins the body even when the blank separator is missing.
    Folded continuation lines (RFC 5322: a value wrapped onto an indented line)
    are stitched back onto the header they continue.
    """
    headers = {}
    body_start = len(block)
    last_key: Optional[str] = None
    for i, line in enumerate(block):
        if line.strip() == "":
            body_start = i + 1
            break
        m = _HEADER_RE.match(line)
        if m:
            # Later duplicate headers win; fine for our well-formed exports.
            last_key = m.group(1).lower()
            headers[last_key] = m.group(2).strip()
        elif last_key is not None and line[:1] in (" ", "\t"):
            # Folded continuation of the previous header value.
            headers[last_key] = (headers[last_key] + " " + line.strip()).strip()
        else:
            # A non-header, non-continuation line ends the header area even with
            # no blank separator (malformed export). The rest is the body.
            body_start = i
            break

    body = "\n".join(block[body_start:]).strip()

    if not headers and not body:
        return None

    return Message(
        sender=headers.get("from", ""),
        timestamp=headers.get("sent") or headers.get("date", ""),
        recipient=headers.get("to", ""),
        subject=headers.get("subject", ""),
        attachments=_split_attachments(headers.get("attachments", "")),
        body=body,
        message_id=headers.get("message-id", ""),
        in_reply_to=headers.get("in-reply-to", ""),
        references=_split_references(headers.get("references", "")),
    )


def _split_attachments(raw: str) -> List[str]:
    """Split an ``Attachments:`` header value into individual names."""
    if not raw.strip():
        return []
    parts = re.split(r"[;,]", raw)
    return [p.strip() for p in parts if p.strip()]


def _split_references(raw: str) -> List[str]:
    """Split a ``References:`` value into individual message-id tokens.

    The value is a whitespace-separated list of ``<id@host>`` tokens. We keep
    every ``<...>`` token in order; if none are bracketed, fall back to
    whitespace splitting so a stray unbracketed id is not dropped.
    """
    if not raw.strip():
        return []
    tokens = re.findall(r"<[^>]+>", raw)
    if tokens:
        return tokens
    return [t for t in raw.split() if t]
