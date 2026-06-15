"""Reconstruct the actual conversation tree from threading headers.

Dedup decides what to keep by comparing *content* (sender + body fingerprint +
attachments). That is robust even when an export carries no threading metadata,
but on its own it is a heuristic: it argues "these files are redundant" from
content overlap, not from the real reply structure.

When exports preserve RFC 5322 threading headers (``Message-ID`` /
``In-Reply-To`` / ``References``) — and real ``.eml``/``.mbox`` always do — we can
do better. This module rebuilds the genuine reply forest and then *verifies*
dedup against it: every message in the reconstructed conversation must still
live in a file dedup chose to keep. If it does, dedup didn't just look right —
it provably dropped nothing. If it doesn't, we report exactly which message a
content-only collapse would have lost.

Standard library only. Identity within a corpus:

* a message with a ``Message-ID`` is identified by that id;
* a message without one falls back to dedup's content key.

(So a message that appears *with* an id in one export and *without* one in
another would count twice — but real mail keeps message-ids consistently, and
the plain-text examples carry none at all, so each corpus is internally
consistent.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .dedup import dedup_directory, message_key
from .parse import Message, find_message_files, parse_path

_ID_RE = re.compile(r"<([^>]+)>")


def _norm_id(raw: str) -> str:
    """Normalize a message-id to a bare, lowercased token (``<a@b>`` -> ``a@b``)."""
    if not raw:
        return ""
    m = _ID_RE.search(raw)
    token = m.group(1) if m else raw
    return token.strip().lower()


def _identity(msg: Message):
    """A hashable identity for a message: its message-id if present, else content."""
    mid = _norm_id(msg.message_id)
    if mid:
        return ("mid", mid)
    return ("body",) + message_key(msg)


def _parent_candidates(msg: Message) -> List[str]:
    """Normalized parent ids to try, nearest-ancestor first.

    ``In-Reply-To`` is the direct parent and wins; ``References`` is the
    root-to-here chain, so its *last* entry is the next-best parent.
    """
    out: List[str] = []
    direct = _norm_id(msg.in_reply_to)
    if direct:
        out.append(direct)
    for ref in reversed(msg.references):
        nid = _norm_id(ref)
        if nid and nid not in out:
            out.append(nid)
    return out


def _who(sender: str) -> str:
    """A short display name for a ``From:`` value (name, else address)."""
    name = re.sub(r"<[^>]+>", "", sender or "").strip()
    if name:
        return name
    m = _ID_RE.search(sender or "")
    return (m.group(1) if m else (sender or "")).strip() or "Unknown"


def _ts(msg: Message) -> str:
    return msg.timestamp or ""


@dataclass
class ThreadNode:
    identity: Tuple
    message: Message
    children: List["ThreadNode"] = field(default_factory=list)
    depth: int = 0

    @property
    def subject(self) -> str:
        return self.message.subject or "(no subject)"


def build_forest(messages: List[Message]) -> List[ThreadNode]:
    """Build the reply forest from a flat list of messages.

    Messages are de-duplicated by :func:`_identity` (earliest timestamp wins, so
    a message is shown once, at its first send). Each node is linked to its
    parent via ``In-Reply-To``/``References``; messages whose parent is unknown
    (the thread openers, or replies whose parent wasn't exported) become roots.
    """
    # De-duplicate to one representative per identity, earliest first.
    best: Dict[Tuple, Message] = {}
    for msg in messages:
        ident = _identity(msg)
        if ident not in best or _ts(msg) < _ts(best[ident]):
            best[ident] = msg

    nodes: Dict[Tuple, ThreadNode] = {
        ident: ThreadNode(identity=ident, message=msg) for ident, msg in best.items()
    }

    # Map every known message-id to its node identity so parents resolve.
    by_mid: Dict[str, Tuple] = {}
    for ident, node in nodes.items():
        mid = _norm_id(node.message.message_id)
        if mid:
            by_mid[mid] = ident

    roots: List[ThreadNode] = []
    for ident, node in nodes.items():
        parent_ident: Optional[Tuple] = None
        for cand in _parent_candidates(node.message):
            target = by_mid.get(cand)
            if target is not None and target != ident:
                parent_ident = target
                break
        if parent_ident is None:
            roots.append(node)
        else:
            nodes[parent_ident].children.append(node)

    def sort_key(n: ThreadNode):
        return (_ts(n.message), n.subject)

    def assign_depth(node: ThreadNode, depth: int) -> None:
        node.depth = depth
        node.children.sort(key=sort_key)
        for child in node.children:
            assign_depth(child, depth + 1)

    roots.sort(key=sort_key)
    for root in roots:
        assign_depth(root, 0)
    return roots


def walk(roots: List[ThreadNode]) -> List[ThreadNode]:
    """Pre-order flatten of the forest (parents before children)."""
    out: List[ThreadNode] = []

    def visit(node: ThreadNode) -> None:
        out.append(node)
        for child in node.children:
            visit(child)

    for root in roots:
        visit(root)
    return out


def render_forest(roots: List[ThreadNode]) -> List[str]:
    """ASCII lines for the reconstructed forest, indented by reply depth."""
    lines: List[str] = []
    for node in walk(roots):
        indent = "  " * node.depth
        bullet = "- " if node.depth else "* "
        ts = ("[%s] " % node.message.timestamp) if node.message.timestamp else ""
        lines.append("%s%s%s%s  (%s)" % (indent, bullet, ts, node.subject, _who(node.message.sender)))
    return lines


@dataclass
class VerifyReport:
    """Result of cross-checking dedup's keep-set against the real conversation."""

    files_total: int
    branches_kept: int
    unique_messages: int
    lost: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.lost

    def benchmark_line(self) -> str:
        return "Collapsed %d files -> %d branches; %d unique messages, %d lost." % (
            self.files_total,
            self.branches_kept,
            self.unique_messages,
            len(self.lost),
        )


def _describe(msg: Message) -> str:
    who = _who(msg.sender)
    subject = msg.subject or "(no subject)"
    return "%s: %s" % (who, subject)


def verify_no_loss(directory: str, pattern: Optional[str] = None) -> VerifyReport:
    """Prove dedup's keep-set retains every message in the corpus.

    Identity is message-id when present (authoritative), else dedup's content
    key. ``lost`` lists any message whose identity exists in the corpus but in
    *no* kept branch — i.e. content-only dedup would have discarded it. On the
    intended inputs this is empty, which is the "0 unique messages lost" proof.
    """
    import os

    paths = find_message_files(directory, pattern=pattern)
    per_file: Dict[str, List[Message]] = {}
    for p in paths:
        per_file[os.path.basename(p)] = parse_path(p)

    corpus: Dict[Tuple, Message] = {}
    for msgs in per_file.values():
        for msg in msgs:
            corpus.setdefault(_identity(msg), msg)

    result = dedup_directory(directory, pattern=pattern)
    kept_names = set(result.keep)
    kept_identities = {
        _identity(msg)
        for name, msgs in per_file.items()
        if name in kept_names
        for msg in msgs
    }

    lost = [_describe(msg) for ident, msg in corpus.items() if ident not in kept_identities]
    lost.sort()
    return VerifyReport(
        files_total=len(paths),
        branches_kept=len(result.keep),
        unique_messages=len(corpus),
        lost=lost,
    )


def reconstruct(directory: str, pattern: Optional[str] = None) -> Tuple[List[ThreadNode], VerifyReport]:
    """Parse a folder, rebuild the reply forest, and verify dedup against it."""
    paths = find_message_files(directory, pattern=pattern)
    messages: List[Message] = []
    for p in paths:
        messages.extend(parse_path(p))
    forest = build_forest(messages)
    report = verify_no_loss(directory, pattern=pattern)
    return forest, report
