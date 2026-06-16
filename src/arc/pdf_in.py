"""Best-effort PDF text reading, for emails that were saved/printed to PDF.

This is the one place the toolkit looks *inside* a PDF. It is deliberately
opt-in and best-effort:

* If the optional ``pypdf`` package is installed (``pip install
  'archive-reconstruction-platform[pdf]'``), it is used — robust, real-world
  extraction.
* Otherwise a small **standard-library** reader is used: it inflates
  FlateDecode streams with stdlib ``zlib`` and pulls text out of the content
  streams' text operators. That covers text-based PDFs (most "print/save to
  PDF" emails and simple documents) with zero dependencies, but it will get
  little or nothing from scanned/image PDFs or PDFs with unusual font encodings
  — in which case it prints a one-line hint to install the optional extra.

Unlike ``.txt``/``.eml``/``.mbox``, PDF text extraction is inherently fuzzy
(the same email saved twice can extract slightly differently), so a PDF the
reader can't make sense of is *skipped*, never silently flagged for deletion.
"""
from __future__ import annotations

import os
import re
import sys
import zlib
from typing import List

from .parse import Message, parse_thread

# The minimum amount of extracted text we treat as a successful read. Below this
# we assume extraction failed (scanned/complex PDF) rather than risk a bad read.
_MIN_TEXT = 16

# One-time hint so a run over many hard PDFs doesn't spam the terminal.
_hint_shown = False
#: Notes accumulated this process (also surfaced on stderr) — handy for tests.
NOTES: List[str] = []


def have_pypdf():
    try:
        import pypdf  # noqa: F401
        return True
    except Exception:
        return False


def _hint():
    global _hint_shown
    msg = ("note: a PDF yielded little or no text with the built-in reader. For "
           "scanned or complex PDFs, install the optional extra for more robust "
           "extraction:\n      pip install 'archive-reconstruction-platform[pdf]'")
    NOTES.append(msg)
    if not _hint_shown:
        _hint_shown = True
        sys.stderr.write(msg + "\n")


# --- standard-library extraction -------------------------------------------

_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)


def _inflate(chunk: bytes) -> bytes:
    """Return the chunk inflated if it is zlib/FlateDecode data, else as-is."""
    try:
        return zlib.decompress(chunk)
    except Exception:
        return chunk


def _decode_literal(raw: str) -> str:
    """Decode a PDF literal string body (the text between the parentheses)."""
    out = []
    i, n = 0, len(raw)
    esc = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
           "(": "(", ")": ")", "\\": "\\"}
    while i < n:
        c = raw[i]
        if c == "\\" and i + 1 < n:
            nxt = raw[i + 1]
            if nxt in esc:
                out.append(esc[nxt]); i += 2; continue
            if nxt == "\n":  # line continuation
                i += 2; continue
            if nxt.isdigit():  # octal char code \ddd
                j = i + 1; digits = ""
                while j < n and len(digits) < 3 and raw[j].isdigit():
                    digits += raw[j]; j += 1
                try:
                    out.append(chr(int(digits, 8)))
                except ValueError:
                    pass
                i = j; continue
            out.append(nxt); i += 2; continue
        out.append(c); i += 1
    return "".join(out)


def _extract_content_text(buf: bytes) -> str:
    """Pull visible text out of one decoded content stream, one line per text-
    positioning move — enough for the parser to recover 'From:/Sent:/body'."""
    if b"Tj" not in buf and b"TJ" not in buf:
        return ""
    s = buf.decode("latin-1", "replace")
    lines: List[str] = []
    line: List[str] = []
    pending: List[str] = []
    i, n = 0, len(s)

    def flush_line():
        text = "".join(line).rstrip()
        lines.append(text)
        line.clear()

    while i < n:
        c = s[i]
        if c == "(":  # literal string — scan with depth + escapes
            depth, j, body = 1, i + 1, []
            while j < n and depth:
                ch = s[j]
                if ch == "\\" and j + 1 < n:
                    body.append(s[j:j + 2]); j += 2; continue
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        break
                body.append(ch); j += 1
            pending.append(_decode_literal("".join(body)))
            i = j + 1
            continue
        if c == "<" and i + 1 < n and s[i + 1] != "<":  # hex string
            j = s.find(">", i + 1)
            if j == -1:
                break
            hexs = re.sub(r"\s", "", s[i + 1:j])
            if len(hexs) % 2:
                hexs += "0"
            try:
                pending.append(bytes.fromhex(hexs).decode("latin-1", "replace"))
            except ValueError:
                pass
            i = j + 1
            continue
        if c.isalpha() or c in "'\"*":  # operator token
            j = i
            while j < n and (s[j].isalpha() or s[j] in "'\"*0"):
                j += 1
            op = s[i:j]
            i = j
            if op in ("Tj", "TJ"):
                line.extend(pending); pending.clear()
            elif op in ("'", '"'):           # move to next line, then show
                flush_line(); line.extend(pending); pending.clear()
            elif op in ("Td", "TD", "T*"):    # new line position
                if pending:
                    line.extend(pending); pending.clear()
                flush_line()
            elif op == "ET":
                if pending:
                    line.extend(pending); pending.clear()
                flush_line()
            continue
        i += 1

    if pending or line:
        line.extend(pending)
        flush_line()
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _stdlib_extract(data: bytes) -> str:
    parts = []
    for m in _STREAM_RE.finditer(data):
        text = _extract_content_text(_inflate(m.group(1)))
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _pypdf_extract(data: bytes) -> str:
    import io
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def extract_text(data: bytes) -> str:
    """Extract text from PDF bytes — via ``pypdf`` if installed, else stdlib."""
    if have_pypdf():
        try:
            return _pypdf_extract(data)
        except Exception:
            pass
    return _stdlib_extract(data)


# --- public API ------------------------------------------------------------

def parse_pdf(path: str) -> List[Message]:
    """Read a PDF into messages.

    If the extracted text looks like an exported email thread (it has ``From:``
    header blocks) it is parsed like the ``.txt`` format; otherwise the whole
    document becomes a single message (sender empty, body = the text), so a
    duplicate copy still dedups. Returns ``[]`` if no usable text could be read
    (and prints a hint to install the optional extra) — callers should skip such
    files rather than treat them as empty/redundant.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    text = extract_text(data)
    if len(text.strip()) < _MIN_TEXT:
        if not have_pypdf():
            _hint()
        return []
    messages = parse_thread(text)
    if messages:
        return messages
    return [Message(subject=os.path.basename(path), body=text)]
