"""Turn a folder of exported email threads into timeline data.

This is the bridge between the two halves of the toolkit: it parses every thread
file (:mod:`arc.parse`), **deduplicates the messages** with the same content-key
model the dedup engine uses (:mod:`arc.dedup` — sender + body fingerprint, so a
message that appears in several exports is shown once), then shapes the unique
messages into the timeline schema (:mod:`arc.timeline`).

The result: point it at a messy export folder and get one interactive timeline
of the actual conversation, grouped by subject thread and colored by sender.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

from .dedup import message_key
from .parse import Message, find_message_files, parse_path

# Palette for per-sender colors (the timeline would auto-assign too, but we keep
# the mapping explicit and stable here).
_PALETTE = [
    "#1E88E5", "#E11D48", "#1D9E75", "#7C3AED", "#E89C1B", "#0EA5E9",
    "#DB2777", "#16A34A", "#9333EA", "#0D9488", "#D97706", "#6366F1",
]

_ADDR_RE = re.compile(r"<([^>]+)>")
_DATE_RE = re.compile(r"(\d{4})[-/](\d{2})[-/](\d{2})")
_SUBJECT_PREFIX_RE = re.compile(r"^\s*(re|fw|fwd)\s*:\s*", re.IGNORECASE)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "x"


def _split_sender(raw: str) -> tuple[str, str]:
    """Return (display_name, email) from a ``From:`` value."""
    m = _ADDR_RE.search(raw or "")
    email = (m.group(1).strip().lower() if m else (raw or "").strip().lower())
    name = (raw[: m.start()].strip() if m else (raw or "").strip())
    return (name or email or "Unknown"), (email or name or "unknown")


def _display_name(raw: str) -> str:
    return _split_sender(raw)[0]


def base_subject(subject: str) -> str:
    """Strip repeated ``RE:`` / ``FW:`` / ``FWD:`` prefixes to a conversation key."""
    s = subject or ""
    prev = None
    while s != prev:
        prev = s
        s = _SUBJECT_PREFIX_RE.sub("", s)
    return s.strip()


def _iso_date(timestamp: str) -> str:
    m = _DATE_RE.search(timestamp or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else (timestamp or "")


def _ts_key(timestamp: str):
    """A sortable datetime from a header timestamp (best effort)."""
    ts = (timestamp or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    m = _DATE_RE.search(ts)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return datetime.max


def _snippet(text: str, limit: int) -> str:
    flat = " ".join((text or "").split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"


def _parties(msg: Message) -> str:
    sender = _display_name(msg.sender)
    if msg.recipient:
        return f"{sender} → {_display_name(msg.recipient)}"
    return sender


# Tabs with more conversations than this hide the (long) per-topic legend/filter
# and keep just the Key-events filter.
_LEGEND_LIMIT = 8


def collect_unique_messages(paths: list[str]) -> tuple[list[tuple[Message, str]], int]:
    """Parse all files and keep one representative ``(message, source_path)`` per
    content key — the earliest occurrence, so each message is shown at the first
    time it was sent and links back to the file it came from.
    """
    best: dict[Any, tuple[datetime, Message, str]] = {}
    total = 0
    for path in paths:
        for msg in parse_path(path):
            total += 1
            key = message_key(msg)
            ts = _ts_key(msg.timestamp)
            if key not in best or ts < best[key][0]:
                best[key] = (ts, msg, path)
    items = sorted(best.values(), key=lambda v: v[0])
    uniques = [(msg, path) for _, msg, path in items]
    return uniques, total


def _href_for(path: str, directory: str, link_base: str | None) -> str:
    """A link to a source thread file: a hosted URL under ``link_base`` if given,
    otherwise a local ``file://`` URL."""
    if link_base:
        rel = os.path.relpath(path, directory).replace(os.sep, "/")
        return link_base.rstrip("/") + "/" + rel
    return "file:///" + os.path.abspath(path).replace("\\", "/")


def _make_event(msg: Message, path: str, directory: str, link_base: str | None,
                cat_id: str, is_opener: bool) -> dict[str, Any]:
    """Turn one message into a timeline event, colored by its conversation and
    linked back to its source file.

    The card *title* is the email subject (a short, human-written summary of the
    message); the body content goes into the *summary* line below it.
    """
    name, _ = _split_sender(msg.sender)
    subject = (msg.subject or "").strip() or base_subject(msg.subject) or "(no subject)"
    event: dict[str, Any] = {
        "date": _iso_date(msg.timestamp),
        "title": subject,
        "summary": _snippet(msg.body, 240),
        "parties": _parties(msg),
        "category": cat_id,
        "badge": name,  # who sent it, shown on the card (not the organizing axis)
        # Highlight attachment-bearing messages and conversation openers.
        "importance": 2 if msg.attachments else (1 if is_opener else 0),
        "source": {
            "type": "email",
            "label": "Open thread",
            "href": _href_for(path, directory, link_base),
        },
    }
    if msg.attachments:
        event["attachments"] = list(msg.attachments)
    return event


def _build_groups(
    uniques: list[tuple[Message, str]],
    directory: str,
    link_base: str | None,
    tab_id: str,
    categories: list[dict[str, str]],
    palette: dict[str, int],
) -> list[dict[str, Any]]:
    """Group messages by conversation; each conversation is its own colored category."""
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for msg, path in uniques:
        subject = base_subject(msg.subject) or "(no subject)"
        gid = _slug(subject)
        cat_id = f"topic-{tab_id}-{gid}"
        if gid not in groups:
            categories.append(
                {"id": cat_id, "label": subject, "color": _PALETTE[palette["i"] % len(_PALETTE)]}
            )
            palette["i"] += 1
            groups[gid] = {"id": gid, "label": subject, "category": cat_id, "events": []}
            order.append(gid)
        groups[gid]["events"].append(
            _make_event(
                msg, path, directory, link_base, cat_id, is_opener=not groups[gid]["events"]
            )
        )
    return [groups[gid] for gid in order]


def _tab_label(folder: str) -> str:
    name = re.sub(r"^\d+[-_\s]*", "", folder)  # drop an ordering prefix like "01_"
    name = re.sub(r"[-_]+", " ", name).strip()
    return name.title() if name else folder


def ai_email_inputs(uniques: list[tuple[Message, str]]):
    """Compact per-email records for an AI classifier, plus an id -> (msg, path) map."""
    emails = []
    items: dict[str, tuple[Message, str]] = {}
    for i, (msg, path) in enumerate(uniques, 1):
        eid = "e%d" % i
        items[eid] = (msg, path)
        emails.append({
            "id": eid,
            "date": _iso_date(msg.timestamp),
            "from": _display_name(msg.sender),
            "subject": (msg.subject or "").strip(),
            "snippet": _snippet(msg.body, 160),
        })
    return emails, items


def assemble_categorized(directory: str, items: dict[str, tuple[Message, str]],
                         classification: dict[str, Any], link_base: str | None = None,
                         title: str | None = None) -> dict[str, Any]:
    """Turn an AI classification (categories + per-email assignments) into timeline
    data: one group per category, each email placed by date with a source link."""
    categories: list[dict[str, str]] = []
    label_by_id: dict[str, str] = {}
    for i, c in enumerate(classification.get("categories", [])):
        cid = str(c.get("id") or _slug(c.get("label", "category")))
        label = c.get("label", cid)
        categories.append({"id": cid, "label": label, "color": _PALETTE[i % len(_PALETTE)]})
        label_by_id[cid] = label
    known = {c["id"] for c in categories}

    assignments = {a.get("id"): a for a in classification.get("assignments", [])}

    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for eid, (msg, path) in items.items():
        a = assignments.get(eid, {})
        cid = str(a.get("category") or "")
        if cid not in known:
            cid = "uncategorized"
            if cid not in known:
                categories.append({"id": cid, "label": "Uncategorized", "color": "#6B7280"})
                label_by_id[cid] = "Uncategorized"
                known.add(cid)
        if cid not in groups:
            groups[cid] = {
                "id": cid,
                "label": label_by_id.get(cid, cid),
                "category": cid,
                "events": [],
            }
            order.append(cid)
        subject = (msg.subject or "").strip() or base_subject(msg.subject) or "(no subject)"
        event: dict[str, Any] = {
            "date": _iso_date(msg.timestamp),
            "title": subject,
            "summary": a.get("summary") or _snippet(msg.body, 200),
            "parties": _parties(msg),
            "category": cid,
            "badge": _display_name(msg.sender),
            "importance": int(a.get("importance") or 0),
            "source": {
                "type": "email",
                "label": "Open email",
                "href": _href_for(path, directory, link_base),
            },
        }
        if msg.attachments:
            event["attachments"] = list(msg.attachments)
        groups[cid]["events"].append(event)

    # Groups in the AI's category order, with any extras (e.g. uncategorized) last.
    cat_order = [c["id"] for c in classification.get("categories", []) if c.get("id") in groups]
    ordered = [groups[c] for c in cat_order] + [groups[c] for c in order if c not in cat_order]

    n_cat = len(categories)
    folder = os.path.basename(os.path.normpath(directory))
    default_title = title or classification.get("title")
    return {
        "title": default_title or f"Email threads — {folder}",
        "subtitle": "Organized by AI into %d categor%s · %d email(s)."
                    % (n_cat, "y" if n_cat == 1 else "ies", len(items)),
        "categories": categories,
        "tabs": [{
            "id": "timeline",
            "label": "Timeline",
            "heading": default_title or "Timeline",
            "description": (
                "Emails organized into categories by AI; "
                "refine in-browser or in the draft JSON."
            ),
            "filters": True,
            "groups": ordered,
        }],
    }


def build_timeline_data(directory: str, pattern: str | None = None, title: str | None = None,
                        link_base: str | None = None) -> dict[str, Any]:
    """Build timeline data from a folder of exported email threads.

    If ``directory`` contains subfolders, each subfolder becomes a **tab** (think
    mail folders / labels); otherwise the whole folder renders as one tab. Either
    way, messages are deduplicated by content key, grouped into conversations
    (colored by topic), and each card links back to its source file (a local
    ``file://`` path, or a ``link_base`` URL if provided).
    """
    subdirs: list[str] = []
    if os.path.isdir(directory):
        subdirs = [d for d in sorted(os.listdir(directory))
                   if os.path.isdir(os.path.join(directory, d))]
    if subdirs:
        return _multi_tab_data(directory, subdirs, pattern, title, link_base)
    return _single_tab_data(directory, pattern, title, link_base)


def _conversation_tab(tab_id, label, idx, groups, n_messages, multi):
    show = len(groups) <= _LEGEND_LIMIT
    tab = {
        "id": tab_id,
        "label": ("%d. %s" % (idx, label)) if multi else label,
        "heading": label,
        "description": "%d conversation(s), %d message(s) after dedup." % (len(groups), n_messages),
        "filters": True,
        "legend": show,
        "categoryFilter": show,
        "groups": groups,
    }
    return tab


def timeline_data_from_messages(uniques: list[tuple[Message, str]], total: int | None = None,
                                title: str | None = None, link_base: str | None = None,
                                directory: str = ".", label: str = "Conversations",
                                subtitle: str | None = None) -> dict[str, Any]:
    """Build single-tab timeline data from an already-deduped ``(message, source)``
    list — so callers that hold messages (e.g. the SQLite store) can render
    without re-parsing a folder. Messages are grouped into conversations and
    colored by topic, exactly as the folder path does."""
    if total is None:
        total = len(uniques)
    categories: list[dict[str, str]] = []
    palette = {"i": 0}
    groups = _build_groups(uniques, directory, link_base, "conversations", categories, palette)
    duplicates = max(0, total - len(uniques))
    if subtitle is None:
        subtitle = ("%d unique message(s) (%d duplicate%s collapsed)."
                    % (len(uniques), duplicates, "" if duplicates == 1 else "s"))
    return {
        "title": title or "Email threads",
        "subtitle": subtitle,
        "categories": categories,
        "tabs": [_conversation_tab("conversations", label, 1, groups, len(uniques), multi=False)],
    }


def _single_tab_data(
    directory: str, pattern: str | None, title: str | None, link_base: str | None
) -> dict[str, Any]:
    paths = find_message_files(directory, pattern=pattern)
    uniques, total = collect_unique_messages(paths)
    duplicates = total - len(uniques)
    subtitle = ("Generated from %d thread file(s); %d unique message(s) after dedup "
                "(%d duplicate%s collapsed)."
                % (len(paths), len(uniques), duplicates, "" if duplicates == 1 else "s"))
    return timeline_data_from_messages(
        uniques, total=total,
        title=title or (f"Email threads — {os.path.basename(os.path.normpath(directory))}"),
        link_base=link_base, directory=directory, label="Conversations", subtitle=subtitle,
    )


def _multi_tab_data(
    directory: str, subdirs: list[str], pattern: str | None, title: str | None,
    link_base: str | None,
) -> dict[str, Any]:
    per_folder = []  # (folder, uniques, nfiles, total)
    for sub in subdirs:
        paths = find_message_files(os.path.join(directory, sub), pattern=pattern)
        if not paths:
            continue
        uniques, total = collect_unique_messages(paths)
        per_folder.append((sub, uniques, len(paths), total))

    if not per_folder:
        return _single_tab_data(directory, pattern, title, link_base)

    categories: list[dict[str, str]] = []
    palette = {"i": 0}
    tabs = []
    g_files = g_unique = g_total = 0
    for idx, (sub, uniques, nfiles, total) in enumerate(per_folder, 1):
        groups = _build_groups(uniques, directory, link_base, _slug(sub), categories, palette)
        tabs.append(
            _conversation_tab(_slug(sub), _tab_label(sub), idx, groups, len(uniques), multi=True)
        )
        g_files += nfiles
        g_unique += len(uniques)
        g_total += total

    duplicates = g_total - g_unique
    folder = os.path.basename(os.path.normpath(directory))
    return {
        "title": title or f"Email threads — {folder}",
        "subtitle": "Generated from %d folder(s) / %d file(s); %d unique message(s) after dedup "
                    "(%d duplicate%s collapsed)."
                    % (len(per_folder), g_files, g_unique, duplicates,
                       "" if duplicates == 1 else "s"),
        "categories": categories,
        "tabs": tabs,
    }
