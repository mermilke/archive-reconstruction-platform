# Security

## Threat model in one line

The Archive Reconstruction Platform runs **entirely on your machine** and
**never deletes anything** — it only ever *recommends* a delete list. Your email
exports stay local.

## What the tool does and doesn't do with your data

- **Offline by default.** The core — `dedup`, `tree`, `timeline`,
  `timeline-threads`, `ingest`, `store`, and the local `arc web` UI — makes **no
  network connections**. Files are read from disk, processed in memory, and
  written back to paths you choose.
- **Recommend-only.** `arc dedup` (and the web UI) classify files as *keep* or
  *redundant* and explain why. **No command ever deletes, moves, or modifies
  your source files.** Acting on the recommendation is a manual step you take
  yourself.
- **Unreadable input is never flagged for deletion.** For example, a PDF whose
  text cannot be extracted is skipped rather than treated as empty — the tool
  never recommends deleting a file it could not actually read.
- **Self-contained output.** Generated timelines are single HTML files with no
  external scripts, stylesheets, fonts, or trackers — nothing is fetched when you
  open them.
- **The local web UI binds to localhost.** `arc web` serves on `127.0.0.1` and
  reuses the same recommend-only pipeline; uploaded files are written to a
  temporary working directory, not sent anywhere.

## The one networked feature (opt-in)

`arc organize` is the **only** code path that touches the network. It calls the
Claude API to suggest categories for a folder of emails, and:

- runs **only** when you set `ANTHROPIC_API_KEY` — with no key, it does nothing;
- sends email metadata/snippets to Anthropic's API solely to produce the
  categorization, over HTTPS via the Python standard library (`urllib`); and
- is never required by any other command.

If you do not run `arc organize`, **no email content ever leaves your machine.**
Treat the data you pass to it as you would any third-party API call, and review
[Anthropic's privacy and data-usage terms](https://www.anthropic.com/legal)
before using it on sensitive material.

## Optional dependencies

The core installs with **zero third-party runtime dependencies**. Two opt-in
extras exist and neither is required:

- `[pdf]` — `pypdf`, for more robust PDF text extraction.
- `[dev]` — `ruff`, `mypy`, `coverage`, for contributors only.

## Reporting a vulnerability

If you find a security issue, please **do not open a public issue.** Instead,
report it privately via GitHub's
[**Report a vulnerability**](https://github.com/mermilke/archive-reconstruction-platform/security/advisories/new)
flow (Security → Advisories). I'll acknowledge the report and work with you on a
fix and disclosure timeline.
