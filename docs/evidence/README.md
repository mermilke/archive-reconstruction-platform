# Evidence emails (generated demo asset)

These `.txt` files are the **source emails** behind the live timeline demo
([`../timeline.html`](../timeline.html)). Each timeline card's *"Open email"*
link points to one of them, so the published GitHub Pages demo is fully
clickable.

They are **fully synthetic** (the fictional "Voltera / Drive Assist 3.0" sample)
and **generated** — do not hand-edit. Regenerate with:

```
python scripts/generate_sample_events.py
arc timeline examples/events.json -o docs/timeline.html
```

They live under `docs/` (not `examples/`) because GitHub Pages only serves the
`docs/` directory, and the links are relative to `docs/timeline.html`.
