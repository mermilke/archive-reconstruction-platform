"""Timeline renderer tests: the curated JSON -> self-contained HTML path.

timeline.py is the largest module and the entry point behind `arc timeline
events.json`. Elsewhere it is only smoke-tested through the bridge; these cover
its *own* logic — schema normalization (both the rich object form and the bare
event array), event counting, category resolution, HTML escaping, and the
offline/self-contained guarantee.

Run directly:  python tests/test_timeline.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from arc.timeline import (  # noqa: E402
    build_timeline,
    count_events,
    load_events,
    render_timeline,
)

EVENTS_JSON = os.path.join(ROOT, "examples", "events.json")

# The rich object schema.
RICH = {
    "title": "Demo",
    "categories": [{"id": "eng", "label": "Engineering", "color": "#EF4444"}],
    "tabs": [{
        "id": "t1", "label": "One", "filters": True,
        "groups": [{
            "id": "g1", "label": "G1", "category": "eng",
            "events": [
                {"date": "2025-03-01", "title": "Kickoff", "category": "eng", "importance": 3},
                {"date": "2025-03-08", "title": "Review", "category": "eng", "importance": 1},
            ],
        }],
    }],
}

# The back-compatible bare-array form: {date, group, title, description}.
BARE = [
    {"date": "2025-01-02", "group": "Alpha", "title": "a1", "description": "..."},
    {"date": "2025-01-09", "group": "Alpha", "title": "a2", "description": "..."},
    {"date": "2025-01-15", "group": "Beta", "title": "b1", "description": "..."},
]

# A tab with filters, phases, and a spread of importance/dates — to exercise the
# overview axis, the filter UI, phase sections, and the per-card importance.
PHASED = {
    "title": "Phased",
    "categories": [
        {"id": "eng", "label": "Engineering", "color": "#EF4444"},
        {"id": "val", "label": "Validation", "color": "#10B981"},
    ],
    "tabs": [{
        "id": "t", "label": "T", "filters": True,
        "groups": [{
            "id": "g", "label": "G", "category": "eng",
            "events": [
                {"date": "2025-01-10", "title": "kickoff", "category": "eng",
                 "importance": 1, "phase": "Build"},
                {"date": "2025-02-14", "title": "harden", "category": "eng",
                 "importance": 2, "phase": "Hardening"},
                {"date": "2025-03-20", "title": "signoff", "category": "val",
                 "importance": 3, "phase": "Validation"},
            ],
        }],
    }],
}

# Same shape, but a tab with filters off (and no category declared).
NOFILTERS = {
    "title": "Plain",
    "tabs": [{"id": "t", "label": "T", "groups": [{"id": "g", "label": "G", "events": [
        {"date": "2025-01-01", "title": "only"}]}]}],
}


def test_count_events_both_schema_forms():
    assert count_events(RICH) == 2
    assert count_events(BARE) == 3  # bare array -> one tab, two groups, three events


def test_bare_array_groups_become_one_tab():
    html = render_timeline(BARE)
    for needle in ("Alpha", "Beta", "a1", "a2", "b1"):
        assert needle in html, f"bare-array content {needle!r} missing from render"


def test_render_is_self_contained():
    """No external scripts/styles/fonts — the offline guarantee. (An SVG xmlns of
    http://www.w3.org/... is an identifier, not a fetch, so we look specifically
    for asset references.)"""
    html = render_timeline(RICH).lower()
    assert "<svg" in html, "overview axis SVG should be present"
    for needle in ('src="http', "<link", "@import"):
        assert needle not in html, f"found external asset reference: {needle!r}"


def test_title_is_html_escaped():
    """Title text is data-controlled; it must be escaped, not injected raw."""
    html = render_timeline({"title": "<script>pwn()</script>", "tabs": []})
    assert "<script>pwn()</script>" not in html
    assert "&lt;script&gt;pwn()&lt;/script&gt;" in html


def test_declared_category_color_reaches_the_page():
    assert "#EF4444" in render_timeline(RICH)


def test_undeclared_category_still_renders():
    """An event referencing a category nobody declared gets a palette color
    rather than crashing the render."""
    data = {"tabs": [{"id": "t", "groups": [{"id": "g", "events": [
        {"date": "2025-02-02", "title": "ghosty", "category": "ghost"}]}]}]}
    assert "ghosty" in render_timeline(data)


def test_unparseable_date_does_not_crash():
    data = {"tabs": [{"id": "t", "groups": [{"id": "g", "events": [
        {"date": "not-a-date", "title": "dateless"}]}]}]}
    assert "dateless" in render_timeline(data)


def test_load_and_build_the_committed_events_json():
    data = load_events(EVENTS_JSON)
    n = count_events(data)
    assert n > 0, "examples/events.json should contain events"
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "tl.html")
        written = build_timeline(EVENTS_JSON, out)
        assert written == n, "build_timeline should report the same count as count_events"
        with open(out, encoding="utf-8") as fh:
            html = fh.read()
    assert html.lstrip().lower().startswith("<!doctype html")
    assert "<svg" in html


def test_axis_svg_places_a_dot_per_event():
    """The overview rail is an SVG with a labelled date span and one dot per
    dated event, each carrying a hover tooltip."""
    html = render_timeline(PHASED)
    assert 'class="axis-svg"' in html
    assert "data-lo=" in html and "data-hi=" in html
    assert html.count("<circle") >= 3, "expected one overview dot per dated event"
    assert "<title>" in html, "dots should carry hover tooltips"


def test_filters_ui_present_only_when_enabled():
    on = render_timeline(PHASED)
    assert 'class="filters"' in on
    assert 'data-cat-filter="all"' in on, "category filter buttons should render"
    assert 'data-key-filter="key"' in on, "the 'key events' filter should render"
    off = render_timeline(NOFILTERS)
    assert 'class="filters"' not in off, "no filter UI when a tab doesn't opt in"


def test_phases_render_as_labelled_sections():
    html = render_timeline(PHASED)
    assert 'class="phase"' in html
    for label in ("Build", "Hardening", "Validation"):
        assert f"<h3>{label}</h3>" in html, f"phase {label!r} should be its own section"


def test_importance_reaches_the_card_dataset():
    """Importance drives dot size / star markers via the card's data-key."""
    html = render_timeline(PHASED)
    assert 'data-key="3"' in html, "the milestone (importance 3) should be tagged"
    assert 'data-key="1"' in html


def main():
    test_count_events_both_schema_forms()
    test_axis_svg_places_a_dot_per_event()
    test_filters_ui_present_only_when_enabled()
    test_phases_render_as_labelled_sections()
    test_importance_reaches_the_card_dataset()
    test_bare_array_groups_become_one_tab()
    test_render_is_self_contained()
    test_title_is_html_escaped()
    test_declared_category_color_reaches_the_page()
    test_undeclared_category_still_renders()
    test_unparseable_date_does_not_crash()
    test_load_and_build_the_committed_events_json()
    print("OK - timeline: both schema forms, counts, self-contained + escaped HTML, "
          "category resolution, overview axis, filter UI, phase sections, importance, "
          "and the committed events.json render.")


if __name__ == "__main__":
    main()
