"""Branch-aware deduplication of exported email threads.

The crown-jewel idea: reduce each file to a **set of content keys**.

* one key per message     = sender + a fingerprint of the body (timestamps ignored)
* one key per attachment  = the distinct attachment name

A file is **redundant** only when its key-set is a subset of another file's
key-set. Files that are a subset of nothing are the **branches** worth keeping;
together they preserve every message and every attachment.

Why this matters: when a conversation forks, the *biggest* file is not
necessarily a superset of the others. A smaller file may carry a reply — or an
attachment — that the big one never had. Comparing key-sets, not byte counts,
is what makes the dedup correct across branches.

The tool only ever **recommends** a delete list. It never deletes anything.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from .normalize import clean_for_fingerprint
from .parse import Message, find_message_files, parse_path

# A content key is a tuple so it is hashable and human-inspectable:
#   ("msg", normalized_sender, body_fingerprint)
#   ("att", "",                normalized_attachment_name)
Key = Tuple[str, str, str]

_ADDR_RE = re.compile(r"<([^>]+)>")


def _normalize_sender(sender: str) -> str:
    """Reduce a ``From:`` value to a stable identity (the email if present)."""
    m = _ADDR_RE.search(sender)
    if m:
        return m.group(1).strip().lower()
    return sender.strip().lower()


def _fingerprint_body(body: str) -> str:
    """Reduce a body to a stable identity fingerprint.

    First strip quoted prior messages and signatures (see :mod:`arc.normalize`)
    so the same message collapses whether or not an export pasted a quote-tail
    onto it, then collapse whitespace and lowercase so trivial reflow does not
    split a message. Timestamps never enter here — that is why timezone-shifted
    duplicates fingerprint identically.
    """
    return " ".join(clean_for_fingerprint(body).split()).lower()


def message_key(msg: Message) -> Key:
    return ("msg", _normalize_sender(msg.sender), _fingerprint_body(msg.body))


def attachment_key(name: str) -> Key:
    return ("att", "", name.strip().lower())


def content_keys(messages: Iterable[Message]) -> Set[Key]:
    """Reduce a parsed file (its messages) to its full set of content keys."""
    keys: Set[Key] = set()
    for msg in messages:
        keys.add(message_key(msg))
        for att in msg.attachments:
            keys.add(attachment_key(att))
    return keys


@dataclass
class FileReport:
    """Per-file verdict."""

    name: str
    keys: Set[Key]
    redundant: bool = False
    superseded_by: List[str] = field(default_factory=list)


@dataclass
class DedupResult:
    reports: List[FileReport]

    @property
    def keep(self) -> List[str]:
        """Names of the branches to keep (subset of nothing)."""
        return [r.name for r in self.reports if not r.redundant]

    @property
    def delete(self) -> List[str]:
        """Names recommended for deletion (each a subset of a kept branch)."""
        return [r.name for r in self.reports if r.redundant]


def analyze(file_keys: Sequence[Tuple[str, Set[Key]]]) -> DedupResult:
    """Decide, for each file, whether it is a redundant subset of another.

    ``file_keys`` is a sequence of ``(name, keyset)`` pairs.

    A file is redundant when its key-set is a *proper* subset of another file's,
    or when it is *equal* to another file's and that other file wins the
    tie-break (lexicographically smaller name is kept). This guarantees that an
    identical-content pair collapses to exactly one keeper.
    """
    items = sorted(file_keys, key=lambda kv: kv[0])  # deterministic ordering
    reports: List[FileReport] = []

    for name, keys in items:
        superseded_by: List[str] = []
        for other_name, other_keys in items:
            if other_name == name:
                continue
            if keys < other_keys:  # strict subset: fully covered by a bigger file
                superseded_by.append(other_name)
            elif keys == other_keys and other_name < name:  # identical: keep one
                superseded_by.append(other_name)
        reports.append(
            FileReport(
                name=name,
                keys=keys,
                redundant=bool(superseded_by),
                superseded_by=superseded_by,
            )
        )

    return DedupResult(reports)


def dedup_directory(path: str, pattern: Optional[str] = None) -> DedupResult:
    """Parse every readable file under ``path`` and run the dedup analysis.

    With no ``pattern``, reads ``.txt``/``.eml``/``.mbox`` and also any
    standalone ``.pdf`` (emails saved/printed to PDF) — *except* a PDF whose name
    matches an attachment referenced by another message, which stays an
    attachment rather than being scanned as its own input. A PDF whose text
    can't be read is skipped (never silently flagged for deletion). PDF reading
    is best-effort and improves with the optional ``[pdf]`` extra; see
    :mod:`arc.pdf_in`.
    """
    import os
    from .parse import collect_directory_messages

    file_keys: List[Tuple[str, Set[Key]]] = [
        (os.path.basename(p), content_keys(messages))
        for p, messages in collect_directory_messages(path, pattern=pattern)
    ]
    return analyze(file_keys)
