# Roadmap

Built **deep before broad**: each step deepens credibility before widening
surface area. Item 0 is done; the rest are in priority order.

## 0. v1 — the core toolkit ✅ (done)

`parse` / `dedup` / `timeline` / `cli`, six synthetic example threads (two
branches + four subsets), synthetic `events.json`, a passing dedup test, and the
docs. Zero third-party dependencies. See [DESIGN.md](DESIGN.md).

## 1. `.eml` / `.mbox` ingestion ✅ (done)

Reads real exported formats using the stdlib `email` and `mailbox` modules
(`src/arc/email_in.py`), mapped onto the existing `Message` model so `dedup`,
`timeline-threads`, `ingest`, and `organize` all work unchanged on real mailbox
exports. Handles RFC 2047-encoded subjects, attachments, and HTML-only bodies
(flattened to text). Folder commands now read `.txt`, `.eml`, and `.mbox` by
default. See `examples/raw_email/` and `tests/test_email_in.py`.

## 2. Harden + spec the parser ✅ (done)

Body identity is now normalized before fingerprinting (`src/arc/normalize.py`):
quoted-reply attribution (`On <date>, <person> wrote:`), `-----Original
Message-----` / `----- Forwarded message -----` blocks, `>`-quoted lines, and
`-- ` signatures are stripped, so the same message collapses regardless of
quote-tail, signature, or timezone. The parser also tolerates malformed blocks
(missing blank line between headers and body) and RFC 5322 folded header lines.
Each behavior is pinned to a synthetic messy fixture (`tests/fixtures/messy/`)
with edge-case tests (`tests/test_parse_hardening.py`): empty file, no-`From`
block, malformed/folded headers, quoted-reply and forwarded-block stripping,
signature stripping, time-zone duplicate collapse, and identical-content
tie-break. The full body is preserved on the `Message` for display — only the
dedup fingerprint sees the cleaned text.

## 3. Thread-tree reconstruction ✅ (done)

`Message` now carries `Message-ID` / `In-Reply-To` / `References` (captured by
both `parse.py` and `email_in.py`). `src/arc/thread.py` rebuilds the actual
reply forest from those headers — falling back to content identity when an
export has none — and `arc tree <dir>` prints it. The same module *verifies*
dedup against the reconstructed conversation: identity is the authoritative
`Message-ID` where present, and every message in the corpus must still live in a
kept branch. That turns the keep/delete call from heuristic into **provably
non-lossy**, reported as a benchmark line, e.g. *"Collapsed 3 files -> 2
branches; 5 unique messages, 0 lost."* (and it names any message a content-only
collapse would have dropped, if the heuristic ever disagrees with the headers).
See `tests/fixtures/threaded/` and `tests/test_thread.py`.

## 4. SQLite store ✅ (done)

A stdlib `sqlite3` store (`src/arc/store.py`) and an `arc store` command group
that accumulates content across runs: `store add <dir>` ingests a folder into
the database (idempotent per file path), and `store dedup` / `store timeline` /
`store stats` then read from everything ever ingested — so the toolkit gets a
memory instead of re-scanning one folder. A message's identity in the store is
the same content key dedup uses (stored as the row key), so dedup computed from
the store is identical to dedup over the files, and it works **across formats
and folders** (e.g. an `.eml` that duplicates a `.txt` thread is flagged). The
existing `ingest` (folder → editable draft JSON) is unchanged — the store is its
own `store` namespace. See `tests/test_store.py`.

## 5. Thin local web UI ✅ (done)

Drag-drop an export, see the branch-aware keep/delete call, hand-pick the
threads you care about, and browse a timeline of just those — all in the
browser (`src/arc/web.py`, `arc web`). The zero-dependency rule was *allowed* to
relax here for a framework, but it didn't need to: the UI runs on the stdlib
`http.server` alone — **no Flask/FastAPI, still zero pip installs**. The server
writes dropped files into a temp working dir and reuses the exact folder
pipeline the CLI uses (`dedup_directory`, `collect_unique_messages`,
`timeline_data_from_messages`, `render_timeline`), so the web verdict is
identical to `arc dedup` by construction. It binds to localhost, makes no
outbound connection, and still only *recommends* a delete set. See
`tests/test_web.py` (upload reproduces `dedup_directory`, selection builds a
timeline, unsupported types are skipped, and the HTTP surface round-trips).

The browser reads each dropped file as text and POSTs JSON rather than using a
`multipart/form-data` upload — the stdlib `cgi` parser was removed in Python
3.13, and every input format here (`.txt`/`.eml`/`.mbox`) is text anyway.

---

## Vision (NOT built — noted here only)

These are deliberately out of scope. They require hosted infrastructure, secure
token storage, and a real security review — the wrong cost/benefit trade for a
local, offline toolkit right now.

- **Live mailbox connect** via Gmail / Outlook OAuth
- **IMAP pull** of a folder or label
- **Forward-to-an-address** ingestion (mail a thread in, it gets processed)

If these ever happen, they belong behind an explicit opt-in with their own
threat model — not bolted onto the offline core.
