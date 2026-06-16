# Attachment files (generated demo asset)

These are **placeholder attachment files** for the live timeline demo
([`../timeline.html`](../timeline.html)). Each attachment chip on a timeline card
links here, so the published GitHub Pages demo is fully clickable.

The attachments are **fictional** (part of the synthetic "Voltera / Drive Assist
3.0" sample), so each file is a tiny generated placeholder — a minimal one-page
PDF for `*.pdf`, a short text stub otherwise — that simply states as much. They
are **generated**; do not hand-edit. Regenerate with:

```
python scripts/generate_sample_events.py
arc timeline examples/events.json -o docs/timeline.html
```

They live under `docs/` (not `examples/`) because GitHub Pages only serves the
`docs/` directory, and the links are relative to `docs/timeline.html`.
