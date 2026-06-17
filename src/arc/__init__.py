"""Archive Reconstruction Platform — make sense of a folder full of exported email threads.

Two capabilities:

* :mod:`arc.dedup`    — branch-aware deduplication of exported thread files.
* :mod:`arc.timeline` — a self-contained, tabbed HTML timeline of events.

Everything here runs on the Python standard library: no network, no services,
and no external assets in any generated HTML.
"""

__version__ = "1.1.0"
