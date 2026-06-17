"""Reduce a messy real-world email body to *just this message's* content.

Exported threads paste a lot of text into the body that is not part of the
message itself:

* quoted prior messages, introduced by an attribution line
  (``On <date>, <person> wrote:``) and/or lines prefixed with ``>``;
* forwarded blocks opened by ``-----Original Message-----`` or
  ``----- Forwarded message -----``;
* a trailing signature after the standard ``-- `` delimiter.

All of that is a *copy* of content that already lives elsewhere (the quoted
message is another message in the same thread; the signature repeats on every
message). It is exactly what makes "the same reply, pasted standalone in one
export and with a quote-tail in another" look like two different messages.

So before dedup fingerprints a body, it is cleaned here. The full, original
body is still kept on the :class:`~arc.parse.Message` for display — only the
identity fingerprint sees the trimmed text. Everything is deliberately
conservative: a body with none of these markers comes back unchanged.
"""
from __future__ import annotations

import re

# An attribution line opening a quoted reply, e.g.
#   On Mon, Nov 24, 2025 at 3:30 PM Raj Patel <raj@x> wrote:
# Some clients wrap it across two or three lines, so we also match the start of
# one and look ahead a little for the closing "wrote:".
_ATTRIB_START_RE = re.compile(r"^On\b", re.IGNORECASE)
_WROTE_RE = re.compile(r"\bwrote:\s*$", re.IGNORECASE)

# Forwarded / original-message separators ("-----Original Message-----",
# "----- Forwarded message -----", with any dash run and spacing).
_SEPARATOR_RE = re.compile(
    r"^\s*-{2,}\s*(original message|forwarded message)\s*-{2,}\s*$",
    re.IGNORECASE,
)

# The RFC 3676 signature delimiter: a line that is exactly "--" or "-- ".
_SIG_RE = re.compile(r"^--[ \t]?$")


def _attribution_index(lines: list[str]) -> int | None:
    """Index of the line that opens a quoted-reply attribution, if any.

    Handles the common case where the attribution wraps across up to three
    physical lines (long address lists), e.g.::

        On Mon, Nov 24, 2025 at 3:30 PM Raj Patel
        <raj.patel@voltera.example> wrote:
    """
    for i, line in enumerate(lines):
        if _ATTRIB_START_RE.match(line.strip()):
            window = " ".join(ln.strip() for ln in lines[i : i + 3])
            if _WROTE_RE.search(window) or "wrote:" in window.lower():
                return i
    return None


def strip_quoted(body: str) -> str:
    """Drop quoted prior messages: attribution lines, separators, ``>`` lines."""
    lines = body.splitlines()

    cut = len(lines)
    for i, line in enumerate(lines):
        if _SEPARATOR_RE.match(line):
            cut = i
            break
    attrib = _attribution_index(lines)
    if attrib is not None:
        cut = min(cut, attrib)

    kept = lines[:cut]
    # Drop any stray standalone quoted lines that appear before the cut, too.
    kept = [ln for ln in kept if not ln.lstrip().startswith(">")]
    return "\n".join(kept).strip()


def strip_signature(body: str) -> str:
    """Drop a trailing signature after the ``-- `` delimiter line, if present."""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if _SIG_RE.match(line):
            return "\n".join(lines[:i]).strip()
    return body.strip()


def clean_for_fingerprint(body: str) -> str:
    """Strip quoted material and a signature — what dedup fingerprints on.

    Conservative by construction: a body with no quote attribution, no
    forwarded-message separator, no ``>`` lines, and no ``-- `` signature
    delimiter is returned unchanged (modulo surrounding whitespace).
    """
    return strip_signature(strip_quoted(body))
