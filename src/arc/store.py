"""A persistent SQLite store that accumulates messages across runs.

The folder commands (`dedup`, `timeline-threads`, `ingest`) each re-scan a
directory from scratch. The store gives the toolkit a **memory**: point
``store add`` at a folder today and another folder next week, and the database
holds the union of every unique message ever seen. ``store dedup`` and
``store timeline`` then read from that accumulated set instead of one folder.

Standard library only (``sqlite3``). The dedup model is unchanged: a message's
identity is its content key (sender + body fingerprint, from :mod:`arc.dedup`),
stored verbatim as the row's primary key, so dedup computed *from the store* is
identical to dedup computed over the original files. Threading headers
(``Message-ID`` etc.) ride along as metadata for the timeline and `tree`.

Design notes:

* identity = ``json.dumps(message_key(msg))`` — reversible back into the exact
  key tuple :func:`arc.dedup.analyze` expects.
* re-ingesting a file already in the store refreshes its mappings rather than
  duplicating them, so ``store add`` is idempotent per path.
* the earliest-timestamped occurrence of a message wins as the stored
  representative (matching the bridge's "show it at its first send" rule).
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .bridge import _ts_key
from .dedup import DedupResult, analyze, attachment_key, message_key
from .parse import Message, find_message_files, parse_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,
    basename    TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    identity        TEXT PRIMARY KEY,
    sender          TEXT, timestamp TEXT, recipient TEXT, subject TEXT, body TEXT,
    message_id      TEXT, in_reply_to TEXT, references_json TEXT, attachments_json TEXT,
    first_seen      TEXT
);
CREATE TABLE IF NOT EXISTS file_messages (
    file_id  INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    identity TEXT NOT NULL,
    PRIMARY KEY (file_id, identity)
);
CREATE TABLE IF NOT EXISTS file_attachments (
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name    TEXT NOT NULL,
    PRIMARY KEY (file_id, name)
);
"""


@dataclass
class AddResult:
    files_added: int = 0
    files_refreshed: int = 0
    messages_added: int = 0
    messages_seen: int = 0  # occurrences that matched an already-stored message


def _identity(msg: Message) -> str:
    """A reversible string identity: the JSON of the dedup content key."""
    return json.dumps(list(message_key(msg)))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: str) -> sqlite3.Connection:
    """Open (creating if needed) the store and ensure the schema exists."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def add_files(conn: sqlite3.Connection, paths: list[str], now: str | None = None) -> AddResult:
    """Ingest each file's messages and attachments into the store (accumulating)."""
    stamp = now or _now()
    res = AddResult()
    for path in paths:
        abspath = os.path.abspath(path)
        row = conn.execute("SELECT id FROM files WHERE path = ?", (abspath,)).fetchone()
        if row is not None:
            file_id = row[0]
            # Refresh: drop this file's old mappings so a re-ingest is clean.
            conn.execute("DELETE FROM file_messages WHERE file_id = ?", (file_id,))
            conn.execute("DELETE FROM file_attachments WHERE file_id = ?", (file_id,))
            res.files_refreshed += 1
        else:
            cur = conn.execute(
                "INSERT INTO files (path, basename, ingested_at) VALUES (?, ?, ?)",
                (abspath, os.path.basename(path), stamp),
            )
            file_id = cur.lastrowid
            res.files_added += 1

        for msg in parse_path(path):
            ident = _identity(msg)
            existing = conn.execute(
                "SELECT timestamp, message_id FROM messages WHERE identity = ?", (ident,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO messages (identity, sender, timestamp, recipient, subject, body, "
                    "message_id, in_reply_to, references_json, attachments_json, first_seen) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (ident, msg.sender, msg.timestamp, msg.recipient, msg.subject, msg.body,
                     msg.message_id, msg.in_reply_to, json.dumps(msg.references),
                     json.dumps(msg.attachments), stamp),
                )
                res.messages_added += 1
            else:
                res.messages_seen += 1
                # Keep the earliest-timestamped occurrence as the representative.
                if _ts_key(msg.timestamp) < _ts_key(existing[0]):
                    conn.execute(
                        "UPDATE messages SET sender=?, timestamp=?, recipient=?, subject=?, "
                        "body=?, in_reply_to=?, references_json=?, attachments_json=? "
                        "WHERE identity=?",
                        (msg.sender, msg.timestamp, msg.recipient, msg.subject, msg.body,
                         msg.in_reply_to, json.dumps(msg.references),
                         json.dumps(msg.attachments), ident),
                    )
                # Backfill a Message-ID if this occurrence has one and the row didn't.
                if msg.message_id and not existing[1]:
                    conn.execute(
                        "UPDATE messages SET message_id = ? WHERE identity = ?",
                        (msg.message_id, ident),
                    )

            conn.execute(
                "INSERT OR IGNORE INTO file_messages (file_id, identity) VALUES (?, ?)",
                (file_id, ident),
            )
            for name in msg.attachments:
                if name.strip():
                    conn.execute(
                        "INSERT OR IGNORE INTO file_attachments (file_id, name) VALUES (?, ?)",
                        (file_id, name.strip()),
                    )

    conn.commit()
    return res


def add_directory(conn: sqlite3.Connection, directory: str, pattern: str | None = None,
                  recursive: bool = False, now: str | None = None) -> AddResult:
    """Ingest every supported file under ``directory`` into the store."""
    paths = find_message_files(directory, recursive=recursive, pattern=pattern)
    return add_files(conn, paths, now=now)


def _file_keysets(conn: sqlite3.Connection) -> list[tuple[str, set]]:
    """Reconstruct each stored file's content key-set for the dedup analysis.

    Names are disambiguated when two stored paths share a basename, so
    :func:`arc.dedup.analyze` (which keys on the name) stays correct.
    """
    out: list[tuple[str, set]] = []
    seen_names: dict = {}
    for file_id, basename in conn.execute("SELECT id, basename FROM files ORDER BY id"):
        name = basename
        if name in seen_names:
            name = "%s#%d" % (basename, file_id)
        seen_names[name] = True

        keys = set()
        for (ident,) in conn.execute(
            "SELECT identity FROM file_messages WHERE file_id = ?", (file_id,)
        ):
            keys.add(tuple(json.loads(ident)))
        for (att,) in conn.execute(
            "SELECT name FROM file_attachments WHERE file_id = ?", (file_id,)
        ):
            keys.add(attachment_key(att))
        out.append((name, keys))
    return out


def dedup(conn: sqlite3.Connection) -> DedupResult:
    """Run the branch-aware dedup across *every* file in the store."""
    return analyze(_file_keysets(conn))


def load_messages(conn: sqlite3.Connection) -> list[tuple[Message, str]]:
    """Every unique stored message as ``(Message, source_path)``, earliest first.

    The source path is the earliest-ingested file that contained the message, so
    timeline cards link back to where it was first seen.
    """
    items: list[tuple[Message, str]] = []
    for row in conn.execute(
        "SELECT identity, sender, timestamp, recipient, subject, body, message_id, "
        "in_reply_to, references_json, attachments_json FROM messages"
    ):
        msg = Message(
            sender=row[1], timestamp=row[2] or "", recipient=row[3] or "",
            subject=row[4] or "", body=row[5] or "", message_id=row[6] or "",
            in_reply_to=row[7] or "", references=json.loads(row[8] or "[]"),
            attachments=json.loads(row[9] or "[]"),
        )
        src = conn.execute(
            "SELECT f.path FROM file_messages fm JOIN files f ON f.id = fm.file_id "
            "WHERE fm.identity = ? ORDER BY f.id LIMIT 1", (row[0],)
        ).fetchone()
        items.append((msg, src[0] if src else ""))
    items.sort(key=lambda mp: _ts_key(mp[0].timestamp))
    return items


@dataclass
class StoreStats:
    files: int
    messages: int
    attachments: int


def stats(conn: sqlite3.Connection) -> StoreStats:
    files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    attachments = conn.execute("SELECT COUNT(DISTINCT name) FROM file_attachments").fetchone()[0]
    return StoreStats(files=files, messages=messages, attachments=attachments)
