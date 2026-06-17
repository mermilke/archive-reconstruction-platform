# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Renderer and CLI test coverage.** `tests/test_timeline.py` exercises the
  timeline renderer directly — both schema forms (rich object and bare event
  array), event counting, category resolution, HTML escaping, the overview-axis
  SVG, the filter UI, phase sections, per-card importance, the
  self-contained/offline guarantee, and the committed `examples/events.json` —
  and `tests/test_cli.py` drives `arc`'s argument dispatch and exit codes plus
  the cp1252-safe output helper. The suite is now thirteen files.

### Changed

- **Archive dedup counts are derived, not hard-coded.**
  `tests/test_archive_example.py` computes the expected keep/redundant sets from
  the corpus by filename role, so adding a fixture can't silently rot a magic
  number.
- **The test runner caps each file at 300s** (a hung local-server or Node test
  reports a timeout instead of wedging the whole run) and now flags a test that
  exits 0 without printing its summary, closing the exit-code-only blind spot.
- **Maturity classifier is now `4 - Beta`** (was `5 - Production/Stable`) — a
  more honest signal for a v1.x solo project; the package name and feature set
  are unchanged.
- **`examples/mailbox/` is no longer tracked** (regenerate with
  `scripts/generate_sample_mailbox.py`), keeping the source tree code-forward.
- **In-browser dedup tool accessibility (`docs/try.html`).** Status messages use
  an inline `aria-live` banner instead of a blocking `alert()`, and the
  compare/viewer modal gains dialog ARIA, focus-on-open, focus-restore, and a Tab
  focus trap.
- **README tightened** — lighter em-dash and bold density across the
  introduction, the engineering highlights, and the formats section.

## [1.1.0] — 2026-06-17

### Added

- **Lint & type-checking in CI** (`ruff` + `mypy`). A new opt-in `[dev]` extra
  installs the tooling; a separate CI job runs `ruff check` and `mypy` on every
  push and pull request. The **runtime core stays zero-dependency** — the tooling
  is never imported by any code path. README gains ruff/mypy badges. `ruff` and
  `mypy` are clean across the codebase.
- **Test coverage measurement.** The stdlib test runner launches each test as a
  subprocess, so `run_all.py` now wraps each child under `coverage` when
  `COVERAGE_PROCESS_START` is set (combine the per-process data files afterwards).
  A CI step reports coverage and enforces a 65% floor (~72% today). See
  `CONTRIBUTING.md`.
- **`SECURITY.md` and `CONTRIBUTING.md`.** Security states the threat model
  plainly (fully local, recommend-only, the only networked path is opt-in
  `arc organize`) and how to report a vulnerability; Contributing documents the
  zero-runtime-dependency hard rule, dev setup via the `[dev]` extra, the test
  runner, lint/type-check, and the "every feature ships a test" convention.
- **"Engineering highlights" README section** with headline metrics, each linked
  to the test that asserts it.
- **pipx install quickstart** in the README (`pip install --user` leaves console
  scripts off PATH; pipx fixes it).

- **Timeline focus & fullscreen in the local web UI.** The `arc web` timeline
  preview gains a **Focus timeline** toggle (collapses the uploader and the
  files/dedup panel so the timeline spans the full width and height) and a
  **Fullscreen** button (true browser fullscreen for the timeline; Esc exits) —
  for reading a built timeline without the dedup chrome in the way.
- **Folder drag-and-drop in the local web UI.** Dropping a whole export *folder*
  (e.g. `examples/archive`) now works — the browser recurses into the directory
  and uploads every `.txt`/`.eml`/`.mbox`/`.pdf` inside (junk like `.DS_Store` is
  ignored). Previously only loose files dropped one-by-one were read.
- **Save & reopen a timeline.** The web UI gains a **Download** button (saves the
  built timeline as a self-contained `.html`) and **Open saved…** (load a
  previously downloaded timeline back into the preview), so you can keep a
  timeline and reopen it later without re-running the dedup.
- **Back-to-top button on timelines.** Long timelines (standalone and in the web
  UI preview) get a floating up-arrow that appears once you scroll down and jumps
  smoothly back to the top.
- **In-browser dedup tool** (`docs/try.html`) — a zero-install web page that runs
  the branch-aware dedup entirely client-side: drag in `.txt` thread exports (or
  click *Load the sample data*) and get the keep/delete verdict plus a
  side-by-side compare of any redundant file against its keeper. The dedup core
  is ported to JavaScript (`docs/arc-dedup.js`); files never leave the browser,
  nothing is uploaded. A parity test (`tests/test_js_parity.py`) pins the JS port
  to the Python `arc dedup` verdict on the example corpus so the two can't drift.
- **GitHub Pages landing page** (`docs/index.html`) linking to the dedup tool and
  the timeline demo; the timeline moved to `docs/timeline.html`.
- **Mixed-format example archive** (`examples/archive/`, generated by
  `scripts/generate_example_archive.py`) — a realistic 89-file pile (many
  conversations re-exported across `.txt`, `.eml`, and `.mbox`, emails saved to
  `.pdf`, plus `.pdf`/`.csv`/`.png` attachments) that dedups every readable
  format together: 77 exports collapse to 25 kept branches and 52 redundant
  subsets. It covers the tricky cases — `.eml` subsets of `.txt`/`.mbox` threads,
  `.mbox` timezone-shifted duplicates, re-exports with a quoted-reply tail /
  `-- ` signature / HTML-only body that normalize back onto the plain original, a
  three-way branch where no export is a superset of the others (all kept),
  attachment branching (two files with different attachment sets both kept), and
  **emails saved/printed to PDF** read as inputs (saved-to-PDF excerpts fold in
  as cross-format subsets; a PDF-only conversation is read and kept). Both kinds
  of PDF coexist: a PDF named as an attachment rides along matched by name and is
  never parsed, while a saved-to-PDF email is read by the standard-library
  reader, so the core stays zero-dependency. Covered by
  `tests/test_archive_example.py`.
- **Screenshots in the README** — the web UI dedup verdict and a rendered
  timeline (`docs/img/`).
- **PDF reading (best-effort)** — emails saved/printed to PDF can now be deduped.
  `arc dedup` reads standalone `.pdf` files (a PDF named as another message's
  attachment stays an attachment), parsing a saved email back into messages or
  treating a document as one. The built-in reader is **standard-library only**
  (inflates FlateDecode via `zlib`, extracts text from the content streams), so
  the core stays zero-dependency; an optional extra
  (`pip install "archive-reconstruction-platform[pdf]"`, adds `pypdf`) gives more
  robust extraction. A PDF whose text can't be read is skipped — never flagged
  for deletion — with a one-line hint to install the extra. New module
  `src/arc/pdf_in.py`, covered by `tests/test_pdf_in.py`. The local web UI
  (`arc web`) reads PDFs too — binary files are uploaded base64-encoded and
  decoded server-side. New example folder `examples/pdf_emails/` holds the same
  emails saved across **every** readable format (`.pdf`/`.eml`/`.mbox`/`.txt`) so
  one folder-drag shows format-blind dedup: two PDF copies and an `.eml` of one
  email all collapse together, and a `.txt` export of a message is flagged as a
  subset of the `.mbox` archive that contains it (8 files → 4 kept / 4 redundant).

### Fixed

- **`arc tree` no longer reports phantom losses on mixed-format archives.**
  `verify_no_loss` measured coverage in `Message-ID` space while dedup decides
  deletion in content-key space, so the same message exported *with* a Message-ID
  in one file and *without* one in another looked "lost" even though its content
  was preserved. The verifier now reconciles the two: content kept under a
  different identity is counted as a **collapsed cross-format duplicate**, not a
  loss — e.g. `examples/archive` now verifies as *"0 lost (37 cross-format
  duplicates collapsed)"*. A genuine content loss (content in no kept file) is
  still flagged. Covered by a new mixed-id case in `tests/test_thread.py`.
- **Office/archive attachment placeholders open inline.** The timeline demo's
  `.xlsx`/`.zip`/`.fig` attachment chips downloaded as unopenable archives;
  they're now one-page PDFs served from a `.pdf` href while the chip still shows
  the real name.
- **The timeline demo's source links now work when published.** Every card's
  *"Open email"* link and every attachment chip pointed at paths that GitHub
  Pages doesn't serve (or that didn't exist at all), so they 404'd. The source
  emails now live under `docs/evidence/` and every attachment is a real,
  openable placeholder file under `docs/files/`, both linked relative to
  `docs/timeline.html`. All attachment chips are clickable now (previously some
  were dead).

## [1.0.0] — 2026-06-15

First public release. Zero third-party runtime dependencies — the standard
library does everything in the core.

### Added

- **Branch-aware deduplication** (`arc dedup`). Each file is reduced to a set of
  content keys (sender + body fingerprint, plus one key per attachment); a file
  is redundant only when its key-set is a subset of another's. A forked thread
  that hides a unique reply or attachment is never discarded. Recommends a delete
  list — it never deletes anything.
- **Self-contained interactive timelines** (`arc timeline`). One HTML file with
  tabs, an SVG overview axis, category colours, importance levels, filters,
  grouped phases, and expandable cards — no external assets.
- **Real mailbox ingestion**: `.eml` and `.mbox` via the stdlib `email` /
  `mailbox` modules, plus a stacked `.txt` export format.
- **Hardened parser**: tolerant of quoted replies, forwarded blocks, signatures,
  timezone-shifted duplicates, and malformed/folded headers.
- **Thread-tree reconstruction** (`arc tree`) from `Message-ID` / `In-Reply-To` /
  `References`, which *verifies* dedup loses no message.
- **Accumulating SQLite store** (`arc store`) that dedups across runs, formats,
  and folders.
- **Folder → timeline** (`arc timeline-threads`) and an editable draft export
  (`arc ingest`).
- **Local web UI** (`arc web`): drag-drop an export, see keep/delete, pick
  threads, and browse the timeline — on the stdlib `http.server`, no framework.
- **Opt-in LLM categorizer** (`arc organize`, needs `ANTHROPIC_API_KEY`),
  implemented with stdlib `urllib` so there is still nothing to `pip install`.
  Every other command is fully offline.

[Unreleased]: https://github.com/mermilke/archive-reconstruction-platform/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/mermilke/archive-reconstruction-platform/releases/tag/v1.1.0
[1.0.0]: https://github.com/mermilke/archive-reconstruction-platform/releases/tag/v1.0.0
