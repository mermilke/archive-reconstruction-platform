"""Optional AI-assisted organization for the toolkit.

This is the ONE place the toolkit reaches the network, and it only does so when a
user opts in by setting ``ANTHROPIC_API_KEY``. It calls the Claude API directly
through the Python standard library (``urllib``) — no third-party SDK — so the
package keeps its zero-dependency promise. The entire dedup / timeline / bridge
core stays fully offline; nothing in this module runs unless you ask for it.

Given a list of emails (id, date, sender, subject, snippet), Claude proposes a
small set of topical categories and assigns every email to one, with an
importance rating and a one-line summary. The caller turns that into timeline
data. If no API key is set, callers should fall back to the offline ``ingest``
draft instead.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-4-8"
MAX_TOKENS = 16000


class AIError(RuntimeError):
    """Raised when AI organization can't be performed (no key, network, bad response)."""


def have_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


_SYSTEM = (
    "You organize a folder of exported emails into a timeline. Propose a small, "
    "sensible set of categories that reflect what the emails are ABOUT — topics "
    "or workstreams (for example: Engineering, Legal, Logistics, Finance), not "
    "the people who sent them. Aim for 3 to 8 categories. Assign every email to "
    "exactly one category. Rate each email's importance 0-3 (3 = a milestone or "
    "decision; 0 = routine). Write a neutral one-line summary of each email. Use "
    "only the information given; do not invent details."
)

# A constrained JSON schema so the response is always parseable.
_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "categories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "label": {"type": "string"}},
                "required": ["id", "label"],
                "additionalProperties": False,
            },
        },
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "category": {"type": "string"},
                    "importance": {"type": "integer"},
                    "summary": {"type": "string"},
                },
                "required": ["id", "category", "importance", "summary"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "categories", "assignments"],
    "additionalProperties": False,
}


def build_request(emails: List[Dict[str, Any]], model: str = DEFAULT_MODEL) -> Dict[str, Any]:
    """Build the Claude API request body for organizing ``emails``."""
    user = (
        "Here are the emails as a JSON array. Propose categories and assign each "
        "email to one. Return the assignment for every id.\n\n"
        + json.dumps(emails, ensure_ascii=False)
    )
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": _SYSTEM,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"format": {"type": "json_schema", "schema": _SCHEMA}},
    }


def parse_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and validate the classification JSON from an API response."""
    if data.get("stop_reason") == "max_tokens":
        raise AIError(
            "The model's reply was truncated (too many emails for one pass). "
            "Try a smaller folder, or split it into subfolders."
        )
    text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text = block.get("text", "")
            break
    if not text:
        raise AIError("The API response contained no text to parse.")
    try:
        result = json.loads(text)
    except ValueError as ex:
        raise AIError("The model did not return valid JSON: %s" % ex)
    if not isinstance(result, dict) or "categories" not in result or "assignments" not in result:
        raise AIError("The model's JSON did not have the expected shape.")
    return result


def classify_emails(
    emails: List[Dict[str, Any]],
    *,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    timeout: int = 180,
    transport: Optional[Callable[[Dict[str, Any], str, int], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Ask Claude to organize ``emails`` into categories + per-email assignments.

    ``transport`` is the function that actually performs the HTTP POST; it
    defaults to a stdlib ``urllib`` call and is injectable for testing.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AIError(
            "ANTHROPIC_API_KEY is not set. Set it to use AI organization, or run "
            "`arc ingest <folder> -o draft.json` for an offline draft instead."
        )
    if not emails:
        raise AIError("No emails to organize.")
    body = build_request(emails, model=model)
    post = transport or _post
    data = post(body, api_key, timeout)
    return parse_response(data)


def _post(body: Dict[str, Any], api_key: str, timeout: int) -> Dict[str, Any]:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        detail = ex.read().decode("utf-8", "replace")
        raise AIError("Claude API returned HTTP %s: %s" % (ex.code, detail.strip()[:500]))
    except urllib.error.URLError as ex:
        raise AIError("Network error calling the Claude API: %s" % ex.reason)
