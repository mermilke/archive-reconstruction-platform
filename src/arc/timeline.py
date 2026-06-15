"""Render events into a single self-contained, interactive HTML timeline.

The output is one HTML file with all CSS and JS inlined — no network calls and
no external assets (attachment links, if provided, are the only outbound URLs).
Features, all driven by the data:

* **tabs** — top-level views you switch between
* **overview axis** — an SVG rail per tab; dots placed by date, colored by
  category, sized by importance, with hover tooltips and click-to-jump
* **legend** + **filters** (by category and "key events only")
* **groups** and optional **phases** within a tab
* **event cards** — date / rail-dot / card with title, category badge, parties,
  summary, and an expandable panel (quote, attachment chips, significance note)
* **importance levels** 0-3 -> bigger dots, gold borders, star markers

Data schema (the rich form)::

    {
      "title": "...",
      "subtitle": "...",
      "categories": [{"id": "perception", "label": "Perception ML", "color": "#EF4444"}],
      "tabs": [
        {
          "id": "engineering", "label": "2. Engineering",
          "heading": "...", "description": "...", "filters": true,
          "groups": [
            {
              "id": "perception", "label": "Perception ML", "category": "perception",
              "events": [
                {
                  "date": "2025-03-25", "title": "...",
                  "category": "perception", "badge": "Perception",
                  "parties": "Tomás -> Validation", "summary": "...",
                  "importance": 3, "phase": "Hardening",
                  "quote": "...", "significance": "...",
                  "attachments": [
                    "model_card.pdf",
                    {"name": "manifest.json", "href": "files/manifest.json"}
                  ]
                }
              ]
            }
          ]
        }
      ]
    }

A bare JSON array of ``{date, group, title, description, ...}`` events is also
accepted and rendered as a single tab (back-compatible with the simple form).
"""
from __future__ import annotations

import html as _html
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

E = _html.escape

# Palette for categories that do not declare their own colour.
_PALETTE = [
    "#1E88E5", "#E89C1B", "#1D9E75", "#7C3AED",
    "#C00000", "#0F766E", "#B8860B", "#D81B60",
]
_DEFAULT_CAT = "__default__"

# Vertical stagger for overview dots so neighbours in time do not overlap.
_Y_PATTERN = [30, 48, 66, 38, 58, 34, 52, 70, 44, 62]


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "x"


def _prettify(text: str) -> str:
    return re.sub(r"[-_]+", " ", str(text)).strip().title()


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _tint(h: str, alpha: float) -> str:
    try:
        r, g, b = _hex_to_rgb(h)
    except Exception:
        return "rgba(107,114,128,%s)" % alpha
    return "rgba(%d,%d,%d,%s)" % (r, g, b, alpha)


def _parse_date(value: str):
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _fmt_short(value: str) -> Tuple[str, str]:
    d = _parse_date(value)
    if d is None:
        return (str(value or ""), "")
    return ("%s %d" % (d.strftime("%b"), d.day), str(d.year))


def _fmt_long(d) -> str:
    return "%s %d, %d" % (d.strftime("%b"), d.day, d.year)


def _range_str(events: List[Dict[str, Any]]) -> str:
    dates = [d for d in (_parse_date(str(e.get("date", ""))) for e in events) if d]
    if not dates:
        return ""
    lo, hi = min(dates), max(dates)
    return _fmt_long(lo) if lo == hi else "%s - %s" % (_fmt_long(lo), _fmt_long(hi))


# --------------------------------------------------------------------------- #
# Normalisation + category registry
# --------------------------------------------------------------------------- #
def _normalize(data: Any) -> Dict[str, Any]:
    """Coerce either schema form into the canonical {title, categories, tabs} dict."""
    if isinstance(data, list):
        order: List[str] = []
        buckets: Dict[str, List[Dict[str, Any]]] = {}
        for ev in data:
            group = str(ev.get("group", "Events"))
            buckets.setdefault(group, [])
            if group not in order:
                order.append(group)
            buckets[group].append(ev)
        groups = [
            {"id": _slug(g), "label": g, "category": _slug(g), "events": buckets[g]}
            for g in order
        ]
        return {
            "title": "Archive Reconstruction Timeline",
            "subtitle": "",
            "categories": [],
            "tabs": [
                {
                    "id": "timeline",
                    "label": "Timeline",
                    "heading": "Timeline",
                    "description": "",
                    "filters": True,
                    "groups": groups,
                }
            ],
        }

    if not isinstance(data, dict):
        raise ValueError("events data must be a JSON array or object")
    out = dict(data)
    out.setdefault("categories", [])
    out.setdefault("tabs", [])
    return out


def _build_categories(data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    cats: Dict[str, Dict[str, str]] = {}
    order: List[str] = []

    for c in data.get("categories", []):
        cid = c["id"]
        cats[cid] = {"label": c.get("label", _prettify(cid)), "color": c.get("color")}
        order.append(cid)

    # Discover any category id referenced by groups/events but not declared.
    for tab in data["tabs"]:
        for group in tab.get("groups", []):
            refs = [group.get("category")] + [e.get("category") for e in group.get("events", [])]
            for cid in refs:
                if cid and cid not in cats:
                    cats[cid] = {"label": _prettify(cid), "color": None}
                    order.append(cid)

    palette_i = 0
    for cid in order:
        if not cats[cid]["color"]:
            cats[cid]["color"] = _PALETTE[palette_i % len(_PALETTE)]
            palette_i += 1

    cats[_DEFAULT_CAT] = {"label": "Other", "color": "#6B7280"}
    return cats


def _resolve_cat(event: Dict[str, Any], group_cat: Optional[str], cats: Dict[str, Any]) -> str:
    cat = event.get("category") or group_cat or _DEFAULT_CAT
    return cat if cat in cats else _DEFAULT_CAT


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def load_events(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def count_events(data: Any) -> int:
    data = _normalize(data)
    return sum(len(g.get("events", [])) for tab in data["tabs"] for g in tab.get("groups", []))


def render_timeline(data: Any, title: Optional[str] = None) -> str:
    data = _normalize(data)
    cats = _build_categories(data)

    page_title = title or data.get("title", "Archive Reconstruction Timeline")
    subtitle = data.get("subtitle", "")
    tabs = data["tabs"]

    tab_meta = []  # (pane_id, label)
    panes = []
    for idx, tab in enumerate(tabs):
        pane_id, pane_html, label = _render_tab(tab, cats, idx, active=(idx == 0))
        tab_meta.append((pane_id, label))
        panes.append(pane_html)

    tab_bar = ""
    if len(tab_meta) > 1:
        buttons = []
        for i, (pane_id, label) in enumerate(tab_meta):
            cls = "tab-btn active" if i == 0 else "tab-btn"
            buttons.append(
                '<button class="%s" data-tab="%s" onclick="switchTab(\'%s\',this)">%s</button>'
                % (cls, pane_id, pane_id, E(label))
            )
        tab_bar = '<div class="tab-bar"><div class="tab-btn-group">%s</div></div>' % "".join(buttons)

    html = _PAGE
    html = html.replace("__TITLE__", E(page_title))
    html = html.replace("__SUBTITLE__", E(subtitle))
    html = html.replace("__STOREKEY__", E(_slug(page_title)))
    cats_json = json.dumps({cid: {"label": info["label"], "color": info["color"]}
                            for cid, info in cats.items()})
    html = html.replace("__CATSJSON__", cats_json)
    html = html.replace("__STYLE__", _STYLE)
    html = html.replace("__TABBAR__", tab_bar)
    html = html.replace("__PANES__", "\n".join(panes))
    html = html.replace("__ADDUI__", _ADD_UI)
    html = html.replace("__SCRIPT__", _SCRIPT)
    return html


def build_timeline(events_path: str, output_path: str, title: Optional[str] = None) -> int:
    data = load_events(events_path)
    return write_timeline(data, output_path, title=title)


def write_timeline(data: Any, output_path: str, title: Optional[str] = None) -> int:
    """Render an already-built data dict to ``output_path``; return event count."""
    html = render_timeline(data, title=title)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return count_events(data)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _render_tab(tab: Dict[str, Any], cats: Dict[str, Any], idx: int, active: bool) -> Tuple[str, str, str]:
    tab_id = tab.get("id") or ("tab%d" % idx)
    pane_id = "tab-%s" % tab_id
    label = tab.get("label", tab.get("heading", "Tab %d" % (idx + 1)))

    # First pass: assign stable ids, collect axis dots + which categories appear.
    axis: List[Dict[str, Any]] = []
    used_cats: List[str] = []
    counter = 0
    all_events: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []
    for group in tab.get("groups", []):
        gcat = group.get("category")
        for ev in group.get("events", []):
            counter += 1
            eid = ev.get("id") or ("%s-e%d" % (tab_id, counter))
            ev["__id__"] = eid
            cat = _resolve_cat(ev, gcat, cats)
            if cat not in used_cats:
                used_cats.append(cat)
            all_events.append(ev)
            key = int(ev.get("importance") or 0)
            records.append({
                "label": cats[cat]["label"],
                "key": key,
                "date": str(ev.get("date", "")),
                "title": ev.get("title", ""),
            })
            d = _parse_date(str(ev.get("date", "")))
            if d is not None:
                axis.append(
                    {
                        "id": eid,
                        "ord": d.toordinal(),
                        "iso": d.isoformat(),
                        "title": ev.get("title", ""),
                        "color": cats[cat]["color"],
                        "key": key,
                    }
                )

    overview = _render_overview(tab_id, tab, axis, used_cats, cats, all_events)
    summary = _summary_top(tab, records)
    groups_html = "".join(_render_group(g, tab_id, cats) for g in tab.get("groups", []))
    filtered_panel = _filtered_panel() if tab.get("filters") else ""

    pane = (
        '<div id="%s" class="tab-pane%s">'
        '<div class="pane-header"><h2>%s</h2><p>%s</p></div>'
        "%s%s%s"
        '<div class="detail-wrap"><div class="detail-title">Detail · click any card to expand</div>%s</div>'
        "</div>"
        % (
            pane_id,
            " active" if active else "",
            E(tab.get("heading", label)),
            E(tab.get("description", "")),
            summary,
            overview,
            filtered_panel,
            groups_html,
        )
    )
    return pane_id, pane, label


def _tab_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate full-tab stats: total, date span, category counts, key count."""
    total = len(records)
    dates = [d for d in (_parse_date(r["date"]) for r in records) if d]
    span = ""
    if dates:
        lo, hi = min(dates), max(dates)
        span = _fmt_long(lo) if lo == hi else "%s – %s" % (_fmt_long(lo), _fmt_long(hi))
    counts: Dict[str, int] = {}
    order: List[str] = []
    for r in records:
        label = r["label"]
        if label not in counts:
            counts[label] = 0
            order.append(label)
        counts[label] += 1
    key_recs = sorted(
        [r for r in records if r["key"] >= 2],
        key=lambda r: (0, _parse_date(r["date"]).toordinal()) if _parse_date(r["date"]) else (1, 0),
    )
    key_titles = [r["title"] for r in key_recs if r["title"]]
    busiest = max(order, key=lambda l: counts[l]) if order else ""
    return {
        "total": total,
        "span": span,
        "counts": counts,
        "order": order,
        "ncats": len(order),
        "key": len(key_recs),
        "key_titles": key_titles,
        "busiest": busiest,
    }


def _stats_chips(s: Dict[str, Any]) -> str:
    chips = ['<span class="stat"><b>%d</b> events</span>' % s["total"]]
    if s["span"]:
        chips.append('<span class="stat">%s</span>' % E(s["span"]))
    chips.append('<span class="stat"><b>%d</b> categories</span>' % s["ncats"])
    chips.append('<span class="stat"><b>%d</b> key</span>' % s["key"])
    return '<div class="stats-row">%s</div>' % "".join(chips)


def _overview_paragraph(s: Dict[str, Any]) -> str:
    """A descriptive fallback overview when a tab has no authored ``summary``."""
    if not s["total"]:
        return "No events in this view."
    parts = ["This timeline tracks %d event%s" % (s["total"], "" if s["total"] == 1 else "s")]
    if s["span"]:
        parts.append(" spanning %s" % s["span"])
    parts.append(".")
    if s["ncats"] > 1 and s["busiest"]:
        breakdown = ", ".join("%s (%d)" % (label, s["counts"][label]) for label in s["order"])
        parts.append(" Work splits across %d tracks — %s — led by %s."
                     % (s["ncats"], breakdown, s["busiest"]))
    if s["key_titles"]:
        shown = s["key_titles"][:4]
        names = "; ".join('“%s”' % t for t in shown)
        more = " and %d more" % (len(s["key_titles"]) - len(shown)) if len(s["key_titles"]) > len(shown) else ""
        parts.append(" Key milestones: %s%s." % (names, more))
    elif s["key"]:
        parts.append(" %d event%s flagged as key." % (s["key"], "" if s["key"] == 1 else "s"))
    return "".join(parts)


def _summary_top(tab: Dict[str, Any], records: List[Dict[str, Any]]) -> str:
    """Static, collapsible Summary panel at the top of a tab.

    A paragraph overview (authored ``tab['summary']`` if present, else generated)
    plus a full-tab Stats row. Never changes with the filters.
    """
    s = _tab_stats(records)
    paragraph = tab.get("summary") or _overview_paragraph(s)
    return (
        '<details class="summary-panel" open>'
        '<summary><span class="summary-title">Summary</span></summary>'
        '<p class="summary-text">%s</p>%s'
        "</details>" % (E(str(paragraph)), _stats_chips(s))
    )


def _filtered_panel() -> str:
    """Empty placeholder shown between the overview axis and the detail list,
    only while a filter is active. Filled in by the page's JS from the events
    currently visible.
    """
    return (
        '<section class="summary-filtered" data-filtered-panel hidden>'
        '<span class="summary-title">Filtered view</span>'
        '<p class="summary-text"></p><div class="stats-row"></div>'
        "</section>"
    )


def _render_overview(tab_id, tab, axis, used_cats, cats, all_events) -> str:
    svg = _axis_svg(tab_id, axis)
    legend = _legend(used_cats, cats) if tab.get("legend", True) else ""
    show_cats = tab.get("categoryFilter", True)
    filters = _filters(tab_id, used_cats, cats, show_cats) if tab.get("filters") else ""
    rng = _range_str(all_events)
    hint = '<span class="hint">Hover dots · click to jump</span>' if svg else "<span></span>"
    axis_block = (
        '<div class="axis-wrap" id="axisWrap-%s">%s<div class="tooltip" id="tooltip-%s"></div></div>'
        % (tab_id, svg, tab_id)
        if svg
        else ""
    )
    return (
        '<div class="overview-section">'
        '<div class="overview-title"><span>Overview%s</span>%s</div>'
        "%s%s%s"
        "</div>"
        % (
            (" · " + E(rng)) if rng else "",
            hint,
            axis_block,
            legend,
            filters,
        )
    )


def _axis_svg(tab_id: str, axis: List[Dict[str, Any]]) -> str:
    if not axis:
        return ""
    axis = sorted(axis, key=lambda a: a["ord"])
    lo = axis[0]["ord"]
    hi = axis[-1]["ord"]
    if lo == hi:
        hi = lo + 1

    def x(o: float) -> float:
        return 60.0 + 780.0 * (o - lo) / (hi - lo)

    parts = ['<svg viewBox="0 0 900 130" xmlns="http://www.w3.org/2000/svg" '
             'class="axis-svg" id="svg-%s" data-lo="%s" data-hi="%s">'
             % (tab_id, E(axis[0]["iso"]), E(axis[-1]["iso"]))]
    parts.append('<line x1="60" x2="840" y1="80" y2="80" stroke="#D1D5DB" stroke-width="1"/>')

    for frac in (0.0, 1 / 3, 2 / 3, 1.0):
        o = lo + frac * (hi - lo)
        tx = x(o)
        label = datetime.fromordinal(int(round(o))).strftime("%b %Y")
        parts.append('<line x1="%.1f" x2="%.1f" y1="77" y2="83" stroke="#9CA3AF"/>' % (tx, tx))
        parts.append('<text x="%.1f" y="96" text-anchor="middle" font-size="10" fill="#6B7280">%s</text>'
                     % (tx, label))

    for i, a in enumerate(axis):
        tx = x(a["ord"])
        ty = _Y_PATTERN[i % len(_Y_PATTERN)]
        r = {3: 8.5, 2: 7.0}.get(a["key"], 5.5)
        title = E("%s — %s" % (a["iso"], a["title"]))
        parts.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="80" stroke="#D1D5DB" '
                     'stroke-width="1" opacity="0.5"/>' % (tx, tx, ty))
        parts.append(
            '<a href="#%s"><circle cx="%.1f" cy="%d" r="%s" fill="%s" stroke="white" '
            'stroke-width="1.5"><title>%s</title></circle></a>'
            % (E(a["id"]), tx, ty, r, a["color"], title)
        )
    parts.append("</svg>")
    return "".join(parts)


def _legend(used_cats: List[str], cats: Dict[str, Any]) -> str:
    visible = [c for c in used_cats if c != _DEFAULT_CAT]
    if not visible:
        return ""
    spans = "".join(
        '<span><span class="dot" style="background:%s"></span>%s</span>'
        % (cats[c]["color"], E(cats[c]["label"]))
        for c in visible
    )
    return '<div class="legend">%s<span class="key-tag">★★ = key event</span></div>' % spans


def _filters(tab_id: str, used_cats: List[str], cats: Dict[str, Any], include_categories: bool = True) -> str:
    cat_html = ""
    if include_categories:
        visible = [c for c in used_cats if c != _DEFAULT_CAT]
        cat_btns = ['<button data-cat-filter="all" class="active">All</button>']
        for c in visible:
            cat_btns.append('<button data-cat-filter="%s">%s</button>' % (E(c), E(cats[c]["label"])))
        cat_html = "<label>Filter</label>%s<span class=\"sep\"></span>" % "".join(cat_btns)
    return (
        '<div class="filters" id="filters-%s">'
        "%s"
        '<button data-key-filter="all" class="active">All events</button>'
        '<button data-key-filter="key">Key events ★★+</button>'
        "</div>" % (tab_id, cat_html)
    )


def _render_group(group: Dict[str, Any], tab_id: str, cats: Dict[str, Any]) -> str:
    gcat = group.get("category")
    color = cats[gcat]["color"] if gcat in cats else cats[_DEFAULT_CAT]["color"]
    events = group.get("events", [])
    rng = _range_str(events)
    header = (
        '<div class="group-header" style="background:%s">'
        "<h2>%s</h2>%s"
        '<span class="grp-count">%d event%s</span></div>'
        % (
            color,
            E(group.get("label", "")),
            ('<span class="grp-range">%s</span>' % E(rng)) if rng else "",
            len(events),
            "" if len(events) == 1 else "s",
        )
    )

    body_parts = []
    for phase_label, phase_events in _phase_buckets(events):
        cards = "".join(_card(ev, gcat, cats) for ev in _sorted_by_date(phase_events))
        if phase_label is None:
            body_parts.append(cards)
        else:
            prange = _range_str(phase_events)
            body_parts.append(
                '<div class="phase"><div class="phase-header"><h3>%s</h3>%s</div>%s</div>'
                % (
                    E(phase_label),
                    ('<span class="phase-range">%s</span>' % E(prange)) if prange else "",
                    cards,
                )
            )

    gid = _slug(str(group.get("id") or group.get("label", "")))
    return ('<section class="group-section" id="grp-%s-%s" data-group-label="%s">%s%s</section>'
            % (tab_id, gid, E(group.get("label", "")), header, "".join(body_parts)))


def _phase_buckets(events: List[Dict[str, Any]]) -> List[Tuple[Optional[str], List[Dict[str, Any]]]]:
    if not any(ev.get("phase") for ev in events):
        return [(None, events)]
    order: List[str] = []
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for ev in events:
        p = ev.get("phase") or ""
        buckets.setdefault(p, [])
        if p not in order:
            order.append(p)
        buckets[p].append(ev)
    return [(p or None, buckets[p]) for p in order]


def _sorted_by_date(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(ev):
        d = _parse_date(str(ev.get("date", "")))
        return (0, d.toordinal()) if d else (1, 0)

    return sorted(events, key=key)


def _card(ev: Dict[str, Any], group_cat: Optional[str], cats: Dict[str, Any]) -> str:
    cat = _resolve_cat(ev, group_cat, cats)
    color = cats[cat]["color"]
    key = int(ev.get("importance") or 0)
    badge = ev.get("badge") or cats[cat]["label"]
    ydate, ytime = _fmt_short(str(ev.get("date", "")))
    parties = ev.get("parties", "")
    parties_html = '<div class="event-parties">%s</div>' % E(parties) if parties else ""

    return (
        '<div class="event" id="%s" data-cat="%s" data-cat-label="%s" data-key="%d" data-date="%s">'
        '<div class="event-date"><span class="ydate">%s</span><span class="ytime">%s</span></div>'
        '<div class="event-dot-col"><div class="event-dot" style="background:%s"></div></div>'
        '<div class="event-card">'
        '<div class="event-header"><div class="event-title">%s</div>'
        '<div class="event-badge" style="background:%s;color:%s">%s</div></div>'
        "%s"
        '<div class="event-summary">%s</div>'
        "%s%s"
        "</div></div>"
        % (
            E(ev.get("__id__", "")),
            E(cat),
            E(cats[cat]["label"]),
            key,
            E(str(ev.get("date", ""))),
            E(ydate),
            E(ytime),
            color,
            E(ev.get("title", "")),
            _tint(color, 0.14),
            color,
            E(badge),
            parties_html,
            E(ev.get("summary", "")),
            _source_row(ev),
            _details(ev),
        )
    )


def _source_row(ev: Dict[str, Any]) -> str:
    """Provenance row: a link to the source (email/doc) and/or who added it."""
    src = ev.get("source")
    if not isinstance(src, dict):
        return ""
    typ = src.get("type", "ref")
    href = src.get("href")
    label = src.get("label")
    parts: List[str] = []
    if href:
        icon = "📧" if typ == "email" else "🔗"
        text = label or ("Open email" if typ == "email" else "Open source")
        parts.append('<a class="src-link" href="%s" target="_blank" rel="noopener">%s %s</a>'
                     % (E(str(href)), icon, E(text)))
    elif label:
        parts.append('<span class="src-link src-static">%s</span>' % E(label))
    if typ == "manual" or src.get("by") or src.get("at"):
        meta = "✎ Added by %s" % E(str(src.get("by") or "someone"))
        if src.get("at"):
            meta += " · %s" % E(str(src.get("at")))
        parts.append('<span class="src-meta">%s</span>' % meta)
    if not parts:
        return ""
    return '<div class="event-source">%s</div>' % "".join(parts)


def _details(ev: Dict[str, Any]) -> str:
    parts: List[str] = []
    quote = ev.get("quote")
    if quote:
        parts.append('<div class="quote">%s</div>' % E(str(quote)))

    attachments = ev.get("attachments") or []
    if attachments:
        chips = "".join(_att_chip(a) for a in attachments)
        parts.append('<span class="label">Attachments</span>%s' % chips)

    significance = ev.get("significance")
    if significance:
        parts.append('<div class="significance">%s</div>' % E(str(significance)))

    if not parts:
        return ""
    return '<details class="event-extra"><summary>show details</summary>%s</details>' % "".join(parts)


def _att_chip(att: Any) -> str:
    if isinstance(att, dict):
        name = att.get("name", "")
        href = att.get("href")
    else:
        name, href = str(att), None
    if href:
        return ('<a class="file-chip" href="%s" target="_blank" rel="noopener">%s</a>'
                % (E(str(href)), E(name)))
    return '<span class="file-chip">%s</span>' % E(name)


# --------------------------------------------------------------------------- #
# Static assets (CSS + JS), inlined
# --------------------------------------------------------------------------- #
_STYLE = """
:root{
  --bg:#FAFAF7;--card:#FFFFFF;--ink:#1F2937;--ink-soft:#4B5563;--ink-muted:#6B7280;
  --ink-faint:#9CA3AF;--line:#E5E7EB;--line-soft:#F3F4F6;--accent:#1F3864;
  --accent-soft:#E8EEF8;--gold:#B8860B;--gold-bg:#FFF8E1;
  --shadow:0 1px 3px rgba(0,0,0,.04),0 1px 2px rgba(0,0,0,.06);
}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5;-webkit-font-smoothing:antialiased}
header{background:var(--card);border-bottom:1px solid var(--line);padding:20px 28px 14px}
header h1{margin:0 0 4px;font-size:21px;color:var(--accent);font-weight:600}
header .subtitle{font-size:12.5px;color:var(--ink-muted)}
.tab-bar{background:#f0f9fb;position:sticky;top:0;z-index:200;box-shadow:0 1px 4px rgba(0,0,0,.08);padding:10px 28px}
.tab-btn-group{display:flex;gap:10px;width:100%}
.tab-btn{flex:1;height:38px;border:none;background:#6acadc;color:#fff;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;padding:0 20px;border-radius:8px;transition:all .2s;white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.tab-btn:hover{background:#3dbdd4}
.tab-btn.active{background:#06a6c4;box-shadow:0 2px 6px rgba(6,166,196,.35)}
.tab-pane{display:none}.tab-pane.active{display:block}
.pane-header{padding:14px 28px 10px;border-bottom:1px solid var(--line);background:var(--card)}
.pane-header h2{margin:0 0 2px;font-size:15px;color:var(--accent);font-weight:600}
.pane-header p{margin:0;font-size:12px;color:var(--ink-muted)}
.overview-section{background:var(--card);border-bottom:1px solid var(--line);padding:20px 28px 24px}
.overview-title{font-size:11px;font-weight:600;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between}
.overview-title .hint{font-weight:400;text-transform:none;letter-spacing:0;color:var(--ink-faint);font-style:italic}
.axis-wrap{position:relative;margin:0 0 4px}
.axis-svg{display:block;width:100%;height:170px}
.axis-svg a circle{opacity:.7;transition:opacity .15s}.axis-svg a:hover circle{opacity:1}
.legend{display:flex;gap:16px;align-items:center;color:var(--ink-muted);font-size:11px;margin-top:12px;flex-wrap:wrap}
.legend span{display:flex;align-items:center;gap:6px}
.legend .dot{width:11px;height:11px;border-radius:50%;flex-shrink:0;border:1.5px solid white;box-shadow:0 0 0 1px var(--line)}
.legend .key-tag{margin-left:auto;color:var(--gold)}
.filters{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:12px}
.filters label{color:var(--ink-muted);font-size:11px;font-weight:500;margin-right:4px}
.filters button{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 10px;font-size:11.5px;color:var(--ink-soft);cursor:pointer;transition:all .15s;font-family:inherit}
.filters button:hover{border-color:var(--accent);color:var(--accent)}
.filters button.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.filters .sep{width:1px;height:18px;background:var(--line);margin:0 4px}
.detail-wrap{max-width:1100px;margin:0 auto;padding:28px 28px 80px}
.detail-title{font-size:11px;font-weight:600;color:var(--ink-muted);text-transform:uppercase;letter-spacing:.06em;margin:0 0 18px}
.group-section{margin-bottom:36px;scroll-margin-top:60px}
.group-header{display:flex;align-items:baseline;gap:12px;padding:10px 16px;border-radius:8px;margin-bottom:18px;color:#fff;flex-wrap:wrap}
.group-header h2{margin:0;font-size:15px;font-weight:600}
.group-header .grp-range{font-size:11.5px;opacity:.85}
.group-header .grp-count{margin-left:auto;font-size:11px;background:rgba(255,255,255,.22);padding:2px 9px;border-radius:10px}
.phase{margin-bottom:22px}
.phase-header{display:flex;align-items:baseline;gap:12px;padding:6px 14px;background:var(--accent-soft);border-radius:6px;margin-bottom:12px;flex-wrap:wrap}
.phase-header h3{margin:0;font-size:13px;color:var(--accent);font-weight:600}
.phase-header .phase-range{color:var(--ink-muted);font-size:11px}
.event{display:grid;grid-template-columns:110px 14px 1fr;gap:14px;margin-bottom:10px;scroll-margin-top:60px}
.event-date{text-align:right;padding-top:12px;color:var(--ink-soft);font-size:11.5px;font-weight:500;line-height:1.3}
.event-date .ydate{display:block;color:var(--accent);font-weight:600}
.event-date .ytime{display:block;color:var(--ink-muted);font-size:10.5px}
.event-dot-col{position:relative;padding-top:16px}
.event-dot{width:12px;height:12px;border-radius:50%;border:2px solid var(--card);box-shadow:0 0 0 1px var(--line);margin:0 auto}
.event[data-key="2"] .event-dot{width:16px;height:16px;margin-top:-2px;box-shadow:0 0 0 3px var(--gold-bg)}
.event[data-key="3"] .event-dot{width:18px;height:18px;margin-top:-3px;box-shadow:0 0 0 4px #FFE699}
.event-card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;box-shadow:var(--shadow);cursor:pointer;transition:border-color .15s,box-shadow .15s}
.event-card:hover{border-color:var(--accent);box-shadow:0 3px 6px rgba(0,0,0,.06)}
.event[data-key="2"] .event-card{border-left:3px solid var(--gold)}
.event[data-key="3"] .event-card{border-left:4px solid var(--gold);background:linear-gradient(to right,var(--gold-bg) 0%,var(--card) 6%)}
.event.highlight .event-card{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.event-header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:4px;flex-wrap:wrap}
.event-title{font-size:13.5px;font-weight:600;color:var(--ink);line-height:1.35}
.event-badge{flex-shrink:0;font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;padding:3px 7px;border-radius:4px;white-space:nowrap}
.event-parties{font-size:11.5px;color:var(--ink-muted);margin-bottom:6px}
.event-summary{font-size:12.5px;color:var(--ink-soft);line-height:1.5}
.event-extra{margin-top:10px;padding-top:10px;border-top:1px solid var(--line-soft);font-size:12px;color:var(--ink-soft)}
.event-extra summary{cursor:pointer;color:var(--accent);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;list-style:none;padding:2px 0;user-select:none}
.event-extra summary::-webkit-details-marker{display:none}
.event-extra summary::before{content:'▶ ';font-size:10px}
.event-extra[open] summary::before{content:'▼ '}
.event-extra .quote{background:var(--line-soft);border-left:3px solid var(--accent);padding:7px 11px;margin:6px 0;font-style:italic;border-radius:0 4px 4px 0;font-size:11.5px}
.event-extra .label{color:var(--ink-muted);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.04em;margin-top:8px;display:block}
.event-extra .file-chip{display:inline-block;background:var(--line-soft);color:var(--ink-soft);padding:2px 7px;border-radius:3px;font-size:10.5px;font-family:ui-monospace,monospace;margin:4px 4px 2px 0;word-break:break-all;text-decoration:none;border:1px solid transparent;transition:all .12s}
.event-extra a.file-chip{background:var(--accent-soft);color:var(--accent)}
.event-extra a.file-chip:hover{border-color:var(--accent);text-decoration:underline}
.event-extra .file-chip::before{content:'📎 ';font-family:initial}
.event-extra .significance{background:var(--gold-bg);border-left:3px solid var(--gold);padding:7px 11px;margin-top:8px;border-radius:0 4px 4px 0;font-size:11.5px;color:#5D4500}
details.summary-panel{margin:16px 28px 0;background:linear-gradient(135deg,#FBFBFE,#F4F8FF);border:1px solid var(--line);border-radius:10px;padding:0 16px;box-shadow:var(--shadow)}
details.summary-panel>summary{cursor:pointer;list-style:none;padding:12px 0;user-select:none;display:flex;align-items:center;gap:8px}
details.summary-panel>summary::-webkit-details-marker{display:none}
details.summary-panel>summary::before{content:'▶';font-size:10px;color:var(--accent)}
details.summary-panel[open]>summary::before{content:'▼'}
.summary-title{font-weight:700;font-size:13px;color:var(--accent)}
.summary-text{font-size:12.5px;color:var(--ink-soft);line-height:1.6;margin:0 0 12px}
.stats-row{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
.stat{background:var(--accent-soft);border:1px solid #DCE6F5;border-radius:6px;padding:4px 10px;font-size:11.5px;color:var(--ink-soft)}
.stat b{color:var(--accent)}
section.summary-filtered{margin:16px 28px 0;background:linear-gradient(135deg,#FFFCF2,#FFF8E1);border:1px solid #F0DEB0;border-radius:10px;padding:14px 16px;box-shadow:var(--shadow)}
section.summary-filtered[hidden]{display:none}
section.summary-filtered .summary-title{display:block;margin-bottom:8px;color:#7A5B00}
section.summary-filtered .summary-text{color:#5D4500;margin-bottom:10px}
section.summary-filtered .stat{background:#FFF3CD;border-color:#F0DEB0;color:#5D4500}
section.summary-filtered .stat b{color:#7A5B00}
.event-source{margin-top:9px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.src-link{display:inline-block;background:#FFF3E0;color:#B85604;padding:3px 9px;border-radius:4px;font-size:10.5px;font-weight:600;text-decoration:none;border:1px solid #FFD8A8;transition:all .12s}
.src-link:hover{background:#FFE0B2;border-color:#B85604;text-decoration:underline}
.src-link.src-static{background:var(--line-soft);color:var(--ink-muted);border-color:transparent;font-weight:500}
.src-meta{font-size:10.5px;color:var(--ink-muted);font-style:italic}
.event-header .event-title{flex:1 1 auto;min-width:0}
.event-actions{display:inline-flex;gap:2px;flex:none;opacity:0;transition:opacity .12s}
.event:hover .event-actions,.event.highlight .event-actions{opacity:1}
.event-actions button{background:none;border:none;cursor:pointer;color:var(--ink-faint);font-size:13px;line-height:1;padding:2px 5px;border-radius:4px}
.event-actions .ev-edit:hover{color:var(--accent);background:var(--accent-soft)}
.event-actions .ev-del:hover{color:#d62027;background:rgba(0,0,0,.06)}
.ett-newcat{display:flex;gap:12px;align-items:flex-end;margin-bottom:12px}
.ett-field input[type=color]{padding:2px;height:38px;width:52px}
.event.manual .event-card{border-left:3px dashed #7C3AED}
.manual-del{margin-left:auto;background:none;border:none;color:var(--ink-faint);cursor:pointer;font-size:14px;line-height:1;padding:2px 4px;border-radius:4px}
.manual-del:hover{color:var(--red,#d62027);background:rgba(0,0,0,.05)}
.add-event-btn{position:fixed;right:22px;bottom:22px;z-index:300;background:var(--accent);color:#fff;border:none;border-radius:999px;padding:12px 18px;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.18)}
.add-event-btn:hover{background:#16264a}
.ett-modal{position:fixed;inset:0;z-index:400;background:rgba(15,23,42,.45);display:none;align-items:center;justify-content:center;padding:20px}
.ett-modal.open{display:flex}
.ett-dialog{background:var(--card);border-radius:12px;box-shadow:0 18px 50px rgba(0,0,0,.3);width:min(520px,100%);max-height:90vh;overflow:auto;padding:20px 22px}
.ett-dialog h3{margin:0 0 4px;font-size:16px;color:var(--accent)}
.ett-dialog .ett-sub{margin:0 0 16px;font-size:12px;color:var(--ink-muted)}
.ett-field{margin-bottom:12px}
.ett-field label{display:block;font-size:11px;font-weight:600;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.ett-field input,.ett-field textarea,.ett-field select{width:100%;box-sizing:border-box;border:1px solid var(--line);border-radius:7px;padding:8px 10px;font-family:inherit;font-size:13px;color:var(--ink);background:var(--bg)}
.ett-field textarea{min-height:64px;resize:vertical}
.ett-row{display:flex;gap:12px}.ett-row .ett-field{flex:1}
.ett-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:18px}
.ett-actions button{font-family:inherit;font-size:13px;font-weight:600;border-radius:7px;padding:8px 16px;cursor:pointer;border:1px solid var(--line)}
.ett-actions .ett-cancel{background:var(--card);color:var(--ink-soft)}
.ett-actions .ett-save{background:var(--accent);color:#fff;border-color:var(--accent)}
@media print{.add-event-btn,.ett-modal{display:none!important}}
.event.filtered-out,.group-section.filtered-out,.phase.filtered-out{display:none}
.tooltip{position:absolute;background:var(--ink);color:#fff;padding:6px 10px;border-radius:4px;font-size:11px;pointer-events:none;opacity:0;transition:opacity .1s;z-index:100;max-width:280px;box-shadow:0 4px 12px rgba(0,0,0,.15)}
.tooltip.visible{opacity:1}
@media print{.tab-bar{display:none}.tab-pane{display:block!important}.event-extra{display:block}.event-extra summary{display:none}.event{page-break-inside:avoid}}
@media(max-width:720px){header,.pane-header,.overview-section,.detail-wrap{padding-left:14px;padding-right:14px}.event{grid-template-columns:70px 12px 1fr;gap:8px}}
""".strip()

_SCRIPT = """
function switchTab(tabId, btn){
  document.querySelectorAll('.tab-pane').forEach(function(p){p.classList.remove('active');});
  document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.remove('active');});
  var pane=document.getElementById(tabId); if(pane) pane.classList.add('active');
  if(btn) btn.classList.add('active');
}
(function(){
  function txt(el,s){var n=el.querySelector(s);return (n?n.textContent:'').trim();}
  function esc(s){return (s||'').replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
  function parseD(s){var m=/^(\\d{4})-(\\d{2})-(\\d{2})/.exec(s||'');return m?new Date(+m[1],+m[2]-1,+m[3]):null;}
  function fmtD(d){return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});}

  function updateFiltered(pane, active){
    var sec=pane.querySelector('[data-filtered-panel]'); if(!sec) return;
    if(!active){ sec.hidden=true; return; }
    var txtEl=sec.querySelector('.summary-text'), stEl=sec.querySelector('.stats-row');
    var all=[].slice.call(pane.querySelectorAll('.event'));
    var vis=all.filter(function(e){return !e.classList.contains('filtered-out');});
    var total=all.length, n=vis.length;
    if(!n){ txtEl.innerHTML='No events match the current filters.'; stEl.innerHTML=''; sec.hidden=false; return; }
    var visSorted=vis.slice().sort(function(a,b){return (parseD(a.dataset.date)||0)-(parseD(b.dataset.date)||0);});
    var ds=visSorted.map(function(e){return parseD(e.dataset.date);}).filter(Boolean);
    var span=ds.length?fmtD(ds[0])+' – '+fmtD(ds[ds.length-1]):'';
    var cats={},order=[];
    vis.forEach(function(e){var l=e.dataset.catLabel||'Other';if(!(l in cats)){cats[l]=0;order.push(l);}cats[l]++;});
    var busiest=order.slice().sort(function(a,b){return cats[b]-cats[a];})[0];
    var keyEls=visSorted.filter(function(e){return parseInt(e.dataset.key||0)>=2;});
    var keyTitles=keyEls.map(function(e){return txt(e,'.event-title');});
    var keyN=keyEls.length;
    var catBtn=pane.querySelector('[data-cat-filter].active');
    var keyBtn=pane.querySelector('[data-key-filter].active');
    var parts=[];
    if(catBtn && catBtn.dataset.catFilter!=='all') parts.push(catBtn.textContent.trim());
    if(keyBtn && keyBtn.dataset.keyFilter==='key') parts.push('key events');
    var desc=parts.join(' + ');
    // Sentence 1: what is selected and over what span.
    var prose=(desc?'<b>Filtered to '+esc(desc)+':</b> showing ':'Showing ')+
      n+' of '+total+' events'+(span?', '+esc(span):'')+'. ';
    // Sentence 2: category breakdown (or sole category).
    if(order.length>1){
      var bd=order.slice().sort(function(a,b){return cats[b]-cats[a];})
        .map(function(l){return esc(l)+' ('+cats[l]+')';}).join(', ');
      prose+='Breakdown: '+bd+'. ';
    } else if(order.length===1){
      prose+='All in <b>'+esc(order[0])+'</b>. ';
    }
    // Sentence 3: name the key milestones in view.
    if(keyN){
      var shown=keyTitles.slice(0,6).map(function(t){return '“'+esc(t)+'”';}).join('; ');
      var more=keyTitles.length>6?(', +'+(keyTitles.length-6)+' more'):'';
      prose+='Key milestone'+(keyN===1?'':'s')+': '+shown+more+'.';
    } else {
      prose+='No key milestones in this selection.';
    }
    txtEl.innerHTML=prose;
    stEl.innerHTML='<span class="stat"><b>'+n+'</b> events</span>'+
      (span?'<span class="stat">'+esc(span)+'</span>':'')+
      '<span class="stat"><b>'+order.length+'</b> categories</span>'+
      '<span class="stat"><b>'+keyN+'</b> key</span>';
    sec.hidden=false;
  }

  function setupSvg(pane, svg, wrap, tip){
    var evData={};
    pane.querySelectorAll('.event').forEach(function(ev){
      var dot=ev.querySelector('.event-dot');
      evData[ev.id]={title:txt(ev,'.event-title'),date:txt(ev,'.ydate')+', '+txt(ev,'.ytime'),
        key:ev.dataset.key||'0',color:(dot?dot.style.background:'')||'#333'};
    });
    svg.querySelectorAll('a').forEach(function(a){
      var m=(a.getAttribute('href')||'').match(/^#(.+)$/); if(!m) return;
      var d=evData[m[1]], c=a.querySelector('circle'); if(!d||!c) return;
      c.style.cursor='pointer';
      function move(e){var r=wrap.getBoundingClientRect();
        tip.style.left=Math.min(e.clientX-r.left+12,r.width-290)+'px';
        tip.style.top=Math.max(0,e.clientY-r.top-60)+'px';}
      c.addEventListener('mouseenter',function(e){
        var stars=d.key==='3'?' · ★★★':d.key==='2'?' · ★★':'';
        tip.innerHTML='<div style="font-size:10px;color:#9CA3AF">'+d.date+stars+'</div>'+
          '<div style="font-weight:600;color:'+d.color+'">'+d.title+'</div>';
        tip.classList.add('visible'); move(e);
      });
      c.addEventListener('mousemove',move);
      c.addEventListener('mouseleave',function(){tip.classList.remove('visible');});
      a.addEventListener('click',function(e){
        e.preventDefault();
        var t=document.getElementById(m[1]); if(!t) return;
        t.classList.add('highlight');
        var det=t.querySelector('details'); if(det) det.open=true;
        t.scrollIntoView({behavior:'smooth',block:'center'});
        setTimeout(function(){t.classList.remove('highlight');},2400);
      });
    });
  }

  function setupFilters(pane, bar, svg){
    var aC='all', aK='all';
    function apply(){
      pane.querySelectorAll('.event').forEach(function(ev){
        var ok=(aC==='all'||ev.dataset.cat===aC)&&(aK==='all'||parseInt(ev.dataset.key||0)>=2);
        ev.classList.toggle('filtered-out',!ok);
      });
      pane.querySelectorAll('.phase').forEach(function(p){
        p.classList.toggle('filtered-out',!p.querySelector('.event:not(.filtered-out)'));});
      pane.querySelectorAll('.group-section').forEach(function(s){
        s.classList.toggle('filtered-out',!s.querySelector('.event:not(.filtered-out)'));});
      if(svg){svg.querySelectorAll('a').forEach(function(a){
        var m=(a.getAttribute('href')||'').match(/^#(.+)$/); if(!m) return;
        var ev=pane.querySelector('#'+m[1]), c=a.querySelector('circle'); if(!c) return;
        c.style.opacity=(!ev||ev.classList.contains('filtered-out'))?'0.18':'1';});}
      updateFiltered(pane, (aC!=='all')||(aK==='key'));
    }
    bar.addEventListener('click', function(e){
      var cb=e.target.closest('[data-cat-filter]');
      if(cb){ bar.querySelectorAll('[data-cat-filter]').forEach(function(x){x.classList.remove('active');});
        cb.classList.add('active'); aC=cb.dataset.catFilter; apply(); return; }
      var kb=e.target.closest('[data-key-filter]');
      if(kb){ bar.querySelectorAll('[data-key-filter]').forEach(function(x){x.classList.remove('active');});
        kb.classList.add('active'); aK=(kb.dataset.keyFilter==='key')?'key':'all'; apply(); return; }
    });
  }

  document.querySelectorAll('.tab-pane').forEach(function(pane){
    var svg=pane.querySelector('.axis-svg'),
        wrap=pane.querySelector('.axis-wrap'),
        tip=pane.querySelector('.tooltip'),
        bar=pane.querySelector('.filters');
    if(svg&&wrap&&tip) setupSvg(pane,svg,wrap,tip);
    if(bar) setupFilters(pane,bar,svg);
  });

  document.querySelectorAll('.event-card').forEach(function(card){
    card.addEventListener('click',function(e){
      if(e.target.closest('a,summary,button')) return;
      var det=card.querySelector('details'); if(det) det.open=!det.open;});
  });

  // ---- in-browser editing (add / edit / delete events, custom categories) ----
  var SKEY='ett-store:'+((document.body.dataset.storeKey)||'timeline');
  var OLDKEY='ett-manual:'+((document.body.dataset.storeKey)||'timeline');
  var STORE=(function(){
    var s; try{ s=JSON.parse(localStorage.getItem(SKEY)); }catch(e){}
    if(!s||typeof s!=='object'){ s={manual:[],overrides:{},categories:[]};
      try{ var old=JSON.parse(localStorage.getItem(OLDKEY)); if(Array.isArray(old)) s.manual=old; }catch(e){} }
    s.manual=s.manual||[]; s.overrides=s.overrides||{}; s.categories=s.categories||[];
    return s;
  })();
  function persist(){ try{ localStorage.setItem(SKEY, JSON.stringify(STORE)); }catch(e){} }
  var CATS=window.ETT_CATS||{};
  function catColor(id){ for(var i=0;i<STORE.categories.length;i++){ if(STORE.categories[i].id===id) return STORE.categories[i].color; } return (CATS[id]&&CATS[id].color)||'#6B7280'; }
  function catLabel(id){ for(var i=0;i<STORE.categories.length;i++){ if(STORE.categories[i].id===id) return STORE.categories[i].label; } return (CATS[id]&&CATS[id].label)||id; }
  function tintc(hex,a){ var h=(hex||'').replace('#',''); if(h.length===3)h=h.split('').map(function(c){return c+c;}).join(''); var r=parseInt(h.slice(0,2),16)||0,g=parseInt(h.slice(2,4),16)||0,b=parseInt(h.slice(4,6),16)||0; return 'rgba('+r+','+g+','+b+','+a+')'; }
  function isManual(id){ for(var i=0;i<STORE.manual.length;i++){ if(STORE.manual[i].id===id) return true; } return false; }
  function manualById(id){ for(var i=0;i<STORE.manual.length;i++){ if(STORE.manual[i].id===id) return STORE.manual[i]; } return null; }
  function shortDate(s){ var d=parseD(s); if(!d) return [s||'','']; return [d.toLocaleDateString('en-US',{month:'short',day:'numeric'}), ''+d.getFullYear()]; }
  function ordinalOf(s){ var m=/(\\d{4})-(\\d{2})-(\\d{2})/.exec(s||''); return m?Date.UTC(+m[1],+m[2]-1,+m[3])/86400000:null; }
  function paneOf(item){ return document.getElementById(item.tab)||document.querySelector('.tab-pane.active'); }
  function activePane(){ return document.querySelector('.tab-pane.active')||document.querySelector('.tab-pane'); }
  function groupById(pane, gid){
    var sec=null;
    if(gid){ try{ sec=pane.querySelector('#'+(window.CSS&&CSS.escape?CSS.escape(gid):gid)); }catch(e){} }
    return sec || pane.querySelector('.group-section');
  }
  function insertByDate(section, el, date){
    var evs=section.querySelectorAll('.event');
    for(var i=0;i<evs.length;i++){
      if(evs[i]===el) continue;
      if((evs[i].dataset.date||'') > (date||'')){ evs[i].parentNode.insertBefore(el, evs[i]); return; }
    }
    var last=evs.length?evs[evs.length-1]:null;
    if(last && last!==el){ last.parentNode.appendChild(el); } else { section.appendChild(el); }
  }
  function addAxisDot(pane, id, date, title){
    var svg=pane.querySelector('.axis-svg'); if(!svg) return;
    var lo=ordinalOf(svg.dataset.lo), hi=ordinalOf(svg.dataset.hi), o=ordinalOf(date);
    if(lo==null||hi==null||o==null) return;
    if(hi===lo) hi=lo+1;
    var x=60+780*(o-lo)/(hi-lo); x=Math.max(60,Math.min(840,x));
    var NS='http://www.w3.org/2000/svg';
    var line=document.createElementNS(NS,'line');
    line.setAttribute('x1',x);line.setAttribute('x2',x);line.setAttribute('y1','20');line.setAttribute('y2','80');
    line.setAttribute('stroke','#7C3AED');line.setAttribute('stroke-width','1');line.setAttribute('opacity','0.5');line.setAttribute('data-manual',id);
    var c=document.createElementNS(NS,'circle');
    c.setAttribute('cx',x);c.setAttribute('cy','20');c.setAttribute('r','6');c.setAttribute('fill','#7C3AED');c.setAttribute('stroke','white');c.setAttribute('stroke-width','1.5');c.setAttribute('data-manual',id);
    var t=document.createElementNS(NS,'title'); t.textContent=(date||'')+' — '+(title||'')+' (added)'; c.appendChild(t);
    svg.appendChild(line); svg.appendChild(c);
  }
  function decorate(card){
    if(!card) return;
    var hdr=card.querySelector('.event-header'); if(!hdr || hdr.querySelector('.event-actions')) return;
    var span=document.createElement('span'); span.className='event-actions';
    span.innerHTML='<button class="ev-edit" title="Edit" data-id="'+esc(card.id)+'">✎</button>'+
                   '<button class="ev-del" title="Remove" data-id="'+esc(card.id)+'">×</button>';
    hdr.appendChild(span);
  }
  function applyCatColor(card, catId){
    var color=catColor(catId);
    var dot=card.querySelector('.event-dot'); if(dot) dot.style.background=color;
    var badge=card.querySelector('.event-badge'); if(badge){ badge.style.background=tintc(color,0.14); badge.style.color=color; }
  }
  function renderManual(item){
    var pane=paneOf(item); if(!pane) return;
    var sec=groupById(pane, item.group); if(!sec) return;
    var ex=document.getElementById(item.id); if(ex) ex.remove();
    var sd=shortDate(item.date);
    var color=item.category?catColor(item.category):'#7C3AED';
    var badgeText=item.category?catLabel(item.category):'Added';
    var meta='✎ Added by '+esc(item.by||'someone')+(item.at?(' · '+esc(item.at)):'');
    var div=document.createElement('div');
    div.className='event manual'; div.id=item.id;
    div.dataset.cat=item.category||'manual'; div.dataset.catLabel=item.category?catLabel(item.category):'Manually added';
    div.dataset.key=String(item.importance||0); div.dataset.date=item.date||'';
    div.innerHTML=
      '<div class="event-date"><span class="ydate">'+esc(sd[0])+'</span><span class="ytime">'+esc(sd[1])+'</span></div>'+
      '<div class="event-dot-col"><div class="event-dot" style="background:'+esc(color)+'"></div></div>'+
      '<div class="event-card"><div class="event-header"><div class="event-title">'+esc(item.title||'(untitled)')+'</div>'+
      '<div class="event-badge" style="background:'+esc(tintc(color,0.14))+';color:'+esc(color)+'">'+esc(badgeText)+'</div></div>'+
      (item.parties?('<div class="event-parties">'+esc(item.parties)+'</div>'):'')+
      (item.summary?('<div class="event-summary">'+esc(item.summary)+'</div>'):'')+
      '<div class="event-source"><span class="src-meta">'+meta+'</span></div></div>';
    insertByDate(sec, div, item.date);
    decorate(div);
    addAxisDot(pane, item.id, item.date, item.title);
  }
  function applyOverride(id, ov){
    var card=document.getElementById(id); if(!card) return;
    if(ov.deleted){ var p0=card.closest('.tab-pane'); card.remove();
      if(p0){ var sv=p0.querySelector('.axis-svg'); if(sv){ var aa=sv.querySelector('a[href="#'+id+'"]'); if(aa) aa.style.display='none'; } }
      return; }
    if(ov.title!=null){ var tt=card.querySelector('.event-title'); if(tt) tt.textContent=ov.title; }
    if(ov.summary!=null){ var sm=card.querySelector('.event-summary');
      if(sm){ sm.textContent=ov.summary; } else if(ov.summary){ var nd=document.createElement('div'); nd.className='event-summary'; nd.textContent=ov.summary;
        var hd=card.querySelector('.event-header'); if(hd && hd.parentNode) hd.parentNode.insertBefore(nd, hd.nextSibling); } }
    if(ov.parties!=null){ var pp=card.querySelector('.event-parties'); if(pp) pp.textContent=ov.parties;
      else if(ov.parties){ var pd=document.createElement('div'); pd.className='event-parties'; pd.textContent=ov.parties;
        var h2=card.querySelector('.event-header'); if(h2&&h2.parentNode) h2.parentNode.insertBefore(pd, h2.nextSibling); } }
    if(ov.importance!=null){ card.dataset.key=String(ov.importance); }
    if(ov.date!=null){ card.dataset.date=ov.date; var s2=shortDate(ov.date); var yd=card.querySelector('.ydate'), yt=card.querySelector('.ytime'); if(yd)yd.textContent=s2[0]; if(yt)yt.textContent=s2[1]; }
    if(ov.category!=null){ card.dataset.cat=ov.category; card.dataset.catLabel=catLabel(ov.category); applyCatColor(card, ov.category); }
    if(ov.editedBy){
      var src=card.querySelector('.event-source');
      if(!src){ src=document.createElement('div'); src.className='event-source'; card.querySelector('.event-card').appendChild(src); }
      var note=src.querySelector('.edit-note');
      if(!note){ note=document.createElement('span'); note.className='src-meta edit-note'; src.appendChild(note); }
      note.textContent='✎ Edited by '+ov.editedBy+(ov.editedAt?(' · '+ov.editedAt):'');
    }
    if(ov.date!=null || ov.group){
      var pane=card.closest('.tab-pane');
      var sec=ov.group?groupById(pane, ov.group):card.closest('.group-section');
      if(sec) insertByDate(sec, card, card.dataset.date||'');
    }
  }
  function refreshPane(pane){
    if(!pane) return;
    var bar=pane.querySelector('.filters'); var aC='all',aK='all';
    if(bar){ var c=bar.querySelector('[data-cat-filter].active'), k=bar.querySelector('[data-key-filter].active');
      aC=c?c.dataset.catFilter:'all'; aK=(k&&k.dataset.keyFilter==='key')?'key':'all'; }
    pane.querySelectorAll('.event').forEach(function(ev){
      var ok=(aC==='all'||ev.dataset.cat===aC)&&(aK==='all'||parseInt(ev.dataset.key||0)>=2);
      ev.classList.toggle('filtered-out',!ok); });
    updateFiltered(pane,(aC!=='all')||(aK==='key'));
  }
  function ensureCatUI(pane, cid){
    if(!cid || !pane) return;
    var bar=pane.querySelector('.filters');
    if(bar && bar.querySelector('[data-cat-filter]') && !bar.querySelector('[data-cat-filter="'+cid+'"]')){
      var sep=bar.querySelector('.sep');
      var btn=document.createElement('button'); btn.setAttribute('data-cat-filter',cid); btn.textContent=catLabel(cid);
      if(sep) bar.insertBefore(btn, sep); else bar.appendChild(btn);
    }
    var legend=pane.querySelector('.legend');
    if(legend && !legend.querySelector('[data-legend="'+cid+'"]')){
      var sp=document.createElement('span'); sp.setAttribute('data-legend',cid);
      sp.innerHTML='<span class="dot" style="background:'+esc(catColor(cid))+'"></span>'+esc(catLabel(cid));
      legend.insertBefore(sp, legend.firstChild);
    }
  }

  // ---- modal (shared by add + edit) ----
  var modal=document.getElementById('ett-modal'), addBtn=document.getElementById('ett-add-btn'), editingId=null;
  function fillGroups(sel, current){
    var pane=activePane(); if(!sel||!pane) return; sel.innerHTML='';
    pane.querySelectorAll('.group-section').forEach(function(s){
      var o=document.createElement('option'); o.value=s.id; o.textContent=s.getAttribute('data-group-label')||s.id;
      if(s.id===current) o.selected=true; sel.appendChild(o); });
  }
  function usedCats(pane){
    var seen={}, out=[];
    pane.querySelectorAll('.event').forEach(function(ev){ var c=ev.dataset.cat; if(c&&c!=='manual'&&!seen[c]){ seen[c]=1; out.push(c); } });
    STORE.categories.forEach(function(c){ if(!seen[c.id]){ seen[c.id]=1; out.push(c.id); } });
    return out;
  }
  function fillCats(sel, current){
    var pane=activePane(); if(!sel||!pane) return; sel.innerHTML='';
    var none=document.createElement('option'); none.value=''; none.textContent='(none)'; sel.appendChild(none);
    usedCats(pane).forEach(function(cid){ var o=document.createElement('option'); o.value=cid; o.textContent=catLabel(cid); if(cid===current)o.selected=true; sel.appendChild(o); });
    var nw=document.createElement('option'); nw.value='__new__'; nw.textContent='➕ New category…'; sel.appendChild(nw);
  }
  function setVal(id,v){ var el=document.getElementById(id); if(el) el.value=v; }
  function getVal(id){ var el=document.getElementById(id); return el?el.value:''; }
  function hideNewCat(){ var n=document.getElementById('ett-newcat'); if(n) n.style.display='none'; setVal('ett-newcat-label',''); }
  function openModal(mode, card){
    if(!modal) return;
    editingId=null;
    var f={date:'',imp:'1',group:'',cat:'',title:'',summary:'',parties:'',by:localStorage.getItem('ett-name')||''};
    document.getElementById('ett-modal-title').textContent=(mode==='edit')?'Edit event':'Add an event';
    document.getElementById('ett-save').textContent=(mode==='edit')?'Save changes':'Add event';
    if(mode==='edit' && card){
      editingId=card.id;
      f.date=card.dataset.date||''; f.imp=String(card.dataset.key||'0');
      var g=card.closest('.group-section'); f.group=g?g.id:'';
      f.cat=(card.dataset.cat&&card.dataset.cat!=='manual')?card.dataset.cat:'';
      f.title=((card.querySelector('.event-title')||{}).textContent||'').trim();
      f.summary=((card.querySelector('.event-summary')||{}).textContent||'').trim();
      f.parties=((card.querySelector('.event-parties')||{}).textContent||'').trim();
    } else { try{ f.date=new Date().toISOString().slice(0,10); }catch(e){} }
    setVal('ett-date',f.date); setVal('ett-imp',f.imp); setVal('ett-title',f.title);
    setVal('ett-summary',f.summary); setVal('ett-parties',f.parties); setVal('ett-by',f.by);
    fillGroups(document.getElementById('ett-group'), f.group);
    fillCats(document.getElementById('ett-cat'), f.cat);
    hideNewCat();
    modal.classList.add('open');
  }
  function closeModal(){ if(modal) modal.classList.remove('open'); editingId=null; }
  var catSel=document.getElementById('ett-cat');
  if(catSel) catSel.addEventListener('change', function(){
    var n=document.getElementById('ett-newcat'); if(n) n.style.display=(catSel.value==='__new__')?'flex':'none';
  });
  if(addBtn) addBtn.addEventListener('click', function(){ openModal('add'); });
  var cancelBtn=document.getElementById('ett-cancel'); if(cancelBtn) cancelBtn.addEventListener('click', closeModal);
  if(modal) modal.addEventListener('click', function(e){ if(e.target===modal) closeModal(); });

  document.addEventListener('click', function(e){
    var ed=e.target.closest('.ev-edit');
    if(ed){ var c1=document.getElementById(ed.dataset.id); if(c1) openModal('edit', c1); return; }
    var dl=e.target.closest('.ev-del');
    if(dl){
      var id=dl.dataset.id, card=document.getElementById(id), pane=card?card.closest('.tab-pane'):null;
      if(isManual(id)){ STORE.manual=STORE.manual.filter(function(x){return x.id!==id;}); }
      else { STORE.overrides[id]=STORE.overrides[id]||{}; STORE.overrides[id].deleted=true; }
      persist();
      if(card) card.remove();
      if(pane){ var svg=pane.querySelector('.axis-svg'); if(svg){
        svg.querySelectorAll('[data-manual="'+id+'"]').forEach(function(n){n.remove();});
        var a=svg.querySelector('a[href="#'+id+'"]'); if(a) a.style.display='none'; } }
      refreshPane(pane);
      return;
    }
  });

  var saveBtn=document.getElementById('ett-save');
  if(saveBtn) saveBtn.addEventListener('click', function(){
    var date=getVal('ett-date'), title=getVal('ett-title').trim(), summary=getVal('ett-summary').trim();
    var parties=getVal('ett-parties').trim(), imp=parseInt(getVal('ett-imp')||'1',10), by=getVal('ett-by').trim();
    var group=getVal('ett-group'), cat=getVal('ett-cat');
    if(!title){ alert('Please enter a title.'); return; }
    if(!date){ alert('Please pick a date.'); return; }
    if(by) localStorage.setItem('ett-name', by);
    if(cat==='__new__'){
      var lbl=getVal('ett-newcat-label').trim(), col=getVal('ett-newcat-color')||'#2563EB';
      if(!lbl){ alert('Enter a name for the new category.'); return; }
      var cid='c'+Date.now()+Math.floor(Math.random()*1000);
      STORE.categories.push({id:cid,label:lbl,color:col}); cat=cid;
    }
    var pane=activePane(); var at=''; try{ at=new Date().toLocaleString(); }catch(e){}
    if(editingId){
      var id=editingId;
      if(isManual(id)){ var it=manualById(id);
        it.date=date; it.title=title; it.summary=summary; it.parties=parties; it.importance=imp; it.group=group; it.category=cat||''; persist();
        renderManual(it);
      } else { var ov=STORE.overrides[id]=STORE.overrides[id]||{};
        ov.date=date; ov.title=title; ov.summary=summary; ov.parties=parties; ov.importance=imp; ov.group=group; if(cat) ov.category=cat; ov.editedBy=by||'you'; ov.editedAt=at; persist();
        applyOverride(id, ov);
      }
      ensureCatUI(pane, cat); refreshPane(pane); closeModal();
      var n1=document.getElementById(id); if(n1){ n1.classList.add('highlight'); setTimeout(function(){n1.classList.remove('highlight');},1600); n1.scrollIntoView({behavior:'smooth',block:'center'}); }
      return;
    }
    var item={ id:'m'+Date.now()+Math.floor(Math.random()*1000), tab:pane?pane.id:'', group:group,
      date:date, title:title, summary:summary, parties:parties, importance:imp, category:cat||'', by:by||'you', at:at };
    STORE.manual.push(item); persist();
    renderManual(item); ensureCatUI(pane, cat); refreshPane(pane); closeModal();
    setVal('ett-title',''); setVal('ett-summary',''); setVal('ett-parties','');
    var nn=document.getElementById(item.id); if(nn) nn.scrollIntoView({behavior:'smooth',block:'center'});
  });

  // ---- initial render: decorate every card, apply saved edits/additions ----
  document.querySelectorAll('.event').forEach(decorate);
  Object.keys(STORE.overrides).forEach(function(id){ applyOverride(id, STORE.overrides[id]); });
  STORE.manual.forEach(renderManual);
  document.querySelectorAll('.tab-pane').forEach(function(pane){
    STORE.categories.forEach(function(c){ if(pane.querySelector('[data-cat="'+c.id+'"]')) ensureCatUI(pane, c.id); });
  });
})();
""".strip()

_ADD_UI = """
<button class="add-event-btn" id="ett-add-btn">➕ Add event</button>
<div class="ett-modal" id="ett-modal">
  <div class="ett-dialog">
    <h3 id="ett-modal-title">Add an event</h3>
    <p class="ett-sub">Saved in this browser and slotted into the timeline by date. The card records who added or edited it and when.</p>
    <div class="ett-row">
      <div class="ett-field"><label>Date</label><input type="date" id="ett-date"></div>
      <div class="ett-field"><label>Importance</label><select id="ett-imp">
        <option value="0">Routine</option>
        <option value="1" selected>Notable</option>
        <option value="2">Key &#9733;&#9733;</option>
        <option value="3">Major &#9733;&#9733;&#9733;</option>
      </select></div>
    </div>
    <div class="ett-row">
      <div class="ett-field"><label>Group</label><select id="ett-group"></select></div>
      <div class="ett-field"><label>Category</label><select id="ett-cat"></select></div>
    </div>
    <div class="ett-newcat" id="ett-newcat" style="display:none">
      <div class="ett-field" style="flex:1"><label>New category</label><input type="text" id="ett-newcat-label" placeholder="e.g. Legal"></div>
      <div class="ett-field"><label>Color</label><input type="color" id="ett-newcat-color" value="#2563EB"></div>
    </div>
    <div class="ett-field"><label>Title</label><input type="text" id="ett-title" placeholder="A short summary"></div>
    <div class="ett-field"><label>Summary</label><textarea id="ett-summary" placeholder="Detail (optional)"></textarea></div>
    <div class="ett-field"><label>Who / participants</label><input type="text" id="ett-parties" placeholder="e.g. Lena &#8594; Raj (optional)"></div>
    <div class="ett-field"><label>Your name</label><input type="text" id="ett-by" placeholder="Added / edited by"></div>
    <div class="ett-actions">
      <button class="ett-cancel" id="ett-cancel">Cancel</button>
      <button class="ett-save" id="ett-save">Add event</button>
    </div>
  </div>
</div>
"""

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
__STYLE__
</style>
</head>
<body data-store-key="__STOREKEY__">
<header>
  <h1>__TITLE__</h1>
  <div class="subtitle">__SUBTITLE__</div>
</header>
__TABBAR__
__PANES__
__ADDUI__
<script>window.ETT_CATS = __CATSJSON__;</script>
<script>
__SCRIPT__
</script>
</body>
</html>
"""
