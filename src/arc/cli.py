"""Command-line entry point for the Archive Reconstruction Platform.

    arc dedup <dir>
    arc timeline <events.json> -o out.html

Invoke as a module:

    python -m arc.cli dedup examples/threads
    python -m arc.cli timeline examples/events.json -o timeline.html
"""
from __future__ import annotations

import argparse
import json
import sys

from .bridge import (
    ai_email_inputs,
    assemble_categorized,
    build_timeline_data,
    collect_unique_messages,
)
from .dedup import dedup_directory
from .parse import find_message_files
from .timeline import build_timeline, count_events, write_timeline


def _print_dedup_result(result, scanned_line: str) -> None:
    """Shared KEEP/DELETE rendering for `dedup` and `store dedup`."""
    keep = result.keep
    delete = result.delete
    print(scanned_line + "\n")

    print("KEEP (%d branch(es) - together these preserve every message and attachment):"
          % len(keep))
    for name in keep:
        print(f"  [keep] {name}")

    keep_set = set(keep)
    print("\nDELETE (%d redundant - each is a subset of a kept branch):" % len(delete))
    if not delete:
        print("  (none)")
    for r in result.reports:
        if r.redundant:
            # Show the kept branch(es) that cover this file, not every container.
            covered_by = [name for name in r.superseded_by if name in keep_set] or r.superseded_by
            print("  [del]  {}   (subset of {})".format(r.name, ", ".join(covered_by)))

    print("\nRecommendation only - no files were deleted.")


def cmd_dedup(args: argparse.Namespace) -> int:
    result = dedup_directory(args.directory, pattern=args.pattern)
    if not result.reports:
        print(f"No files matching {args.pattern!r} found in {args.directory}")
        return 1
    _print_dedup_result(result, "Scanned %d file(s) in %s" % (len(result.reports), args.directory))
    return 0


def cmd_store(args: argparse.Namespace) -> int:
    """SQLite store: accumulate folders across runs, then dedup/timeline from it."""
    from . import store

    conn = store.connect(args.db)
    try:
        if args.store_command == "add":
            res = store.add_directory(conn, args.directory, pattern=args.pattern,
                                      recursive=args.recursive)
            st = store.stats(conn)
            print("Added %d new file(s) (%d refreshed) from %s."
                  % (res.files_added, res.files_refreshed, args.directory))
            print("  %d new unique message(s); %d occurrence(s) already known."
                  % (res.messages_added, res.messages_seen))
            print("Store now holds %d file(s), %d unique message(s), %d attachment(s): %s"
                  % (st.files, st.messages, st.attachments, args.db))
            return 0

        if args.store_command == "stats":
            st = store.stats(conn)
            print("Store %s: %d file(s), %d unique message(s), %d distinct attachment(s)."
                  % (args.db, st.files, st.messages, st.attachments))
            return 0

        if args.store_command == "dedup":
            result = store.dedup(conn)
            if not result.reports:
                print(f"The store is empty. Add files first: arc store add <dir> --db {args.db}")
                return 1
            _print_dedup_result(result, "Dedup across %d file(s) in the store (%s)"
                                % (len(result.reports), args.db))
            return 0

        if args.store_command == "timeline":
            items = store.load_messages(conn)
            if not items:
                print(f"The store is empty. Add files first: arc store add <dir> --db {args.db}")
                return 1
            from .bridge import timeline_data_from_messages
            subtitle = "From the store (%s): %d unique message(s)." % (args.db, len(items))
            data = timeline_data_from_messages(
                items, total=len(items), title=args.title, link_base=args.link_base,
                label="Conversations", subtitle=subtitle,
            )
            count = write_timeline(data, args.output)
            print(subtitle)
            print("Wrote %d event(s) to %s" % (count, args.output))
            return 0

        print(f"Unknown store command: {args.store_command!r}")
        return 1
    finally:
        conn.close()


def _ascii(text: str) -> str:
    """Keep stdout safe on cp1252 consoles (subjects may carry Unicode)."""
    return str(text).encode("ascii", "replace").decode("ascii")


def cmd_tree(args: argparse.Namespace) -> int:
    """Rebuild the conversation tree and prove dedup loses no message.

    Uses Message-ID/In-Reply-To/References when an export preserves them, and
    falls back to content identity otherwise. Prints the reply forest plus a
    benchmark line cross-checking dedup's keep-set against the real thread.
    """
    from .thread import reconstruct, render_forest

    forest, report = reconstruct(args.directory, pattern=args.pattern)
    if not report.files_total:
        print(f"No files matching {args.pattern!r} found in {args.directory}")
        return 1

    roots = len(forest)
    print("Reconstructed %d conversation(s) from %d file(s):\n"
          % (roots, report.files_total))
    for line in render_forest(forest):
        print(_ascii(line))

    print("\n" + report.benchmark_line())
    if report.ok:
        print("Verified: every message in the conversation survives in a kept branch.")
        if report.collapsed:
            print("(%d message(s) re-exported across formats were collapsed by content - "
                  "no content lost.)" % report.collapsed)
        return 0
    print("WARNING: content-only dedup would drop these message(s):")
    for desc in report.lost:
        print(f"  [lost] {_ascii(desc)}")
    return 3


def cmd_timeline(args: argparse.Namespace) -> int:
    count = build_timeline(args.events, args.output, title=args.title)
    print("Wrote %d event(s) to %s" % (count, args.output))
    return 0


def cmd_timeline_threads(args: argparse.Namespace) -> int:
    data = build_timeline_data(
        args.directory, pattern=args.pattern, title=args.title, link_base=args.link_base
    )
    count = write_timeline(data, args.output)
    print("{}".format(data["subtitle"]))
    print("Wrote %d event(s) to %s" % (count, args.output))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Folder -> editable draft timeline-data JSON.

    A first-pass scaffold grouped by conversation and colored by topic. Hand it
    off to a person (or an AI) to refine the categories and placement, then
    render it with ``arc timeline <draft.json> -o out.html``.
    """
    data = build_timeline_data(
        args.directory, pattern=args.pattern, title=args.title, link_base=args.link_base
    )
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("{}".format(data["subtitle"]))
    print("Wrote draft timeline data (%d event(s), %d tab(s)) to %s"
          % (count_events(data), len(data.get("tabs", [])), args.output))
    print(f"Refine the categories/placement, then: arc timeline {args.output} -o out.html")
    return 0


def cmd_organize(args: argparse.Namespace) -> int:
    """Folder -> AI-categorized timeline (opt-in; needs ANTHROPIC_API_KEY).

    Reads every email under the folder, asks Claude to propose categories and
    place each email, and renders the timeline. Falls back with a clear message
    (pointing to `ingest`) when no API key is set.
    """
    from . import ai

    paths = find_message_files(args.directory, recursive=True, pattern=args.pattern)
    if not paths:
        print(f"No files matching {args.pattern!r} under {args.directory}")
        return 1

    uniques, total = collect_unique_messages(paths)
    emails, items = ai_email_inputs(uniques)
    print("Parsed %d file(s); %d unique email(s) after dedup. Asking %s to organize..."
          % (len(paths), len(emails), args.model))

    try:
        classification = ai.classify_emails(emails, model=args.model)
    except ai.AIError as e:
        print(f"\nAI organization unavailable: {e}")
        return 2

    data = assemble_categorized(args.directory, items, classification,
                                link_base=args.link_base, title=args.title)
    if args.draft:
        with open(args.draft, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"Wrote editable draft data to {args.draft}")

    count = write_timeline(data, args.output)
    print("{}".format(data["subtitle"]))
    print("Wrote %d event(s) to %s" % (count, args.output))
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    """Launch the thin local web UI (roadmap item 5).

    Drag-drop an export in the browser, see the keep/delete call, pick the
    threads you want, and browse a timeline of just those. Stdlib http.server
    only (no Flask/FastAPI) — local and offline, like the rest of the toolkit.
    """
    from . import web

    return web.serve(host=args.host, port=args.port, open_browser=not args.no_browser)


def build_parser() -> argparse.ArgumentParser:
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="arc",
        description="Archive Reconstruction Platform: branch-aware dedup and HTML timelines.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_dedup = sub.add_parser(
        "dedup", help="Recommend which exported thread files are redundant subsets."
    )
    p_dedup.add_argument("directory", help="Directory of exported thread files.")
    p_dedup.add_argument(
        "--pattern", default=None,
        help="Glob for input files (default: all of *.txt, *.eml, *.mbox)."
    )
    p_dedup.set_defaults(func=cmd_dedup)

    p_tree = sub.add_parser(
        "tree",
        help="Rebuild the conversation tree from threading headers and verify "
             "dedup loses no message (collapsed X->Y files, 0 lost).",
    )
    p_tree.add_argument("directory", help="Directory of exported thread files.")
    p_tree.add_argument(
        "--pattern", default=None,
        help="Glob for input files (default: all of *.txt, *.eml, *.mbox)."
    )
    p_tree.set_defaults(func=cmd_tree)

    p_store = sub.add_parser(
        "store",
        help="Persistent SQLite store that accumulates messages across runs, then "
             "dedup/timeline from everything ingested.",
    )
    store_sub = p_store.add_subparsers(dest="store_command", required=True)

    s_add = store_sub.add_parser("add", help="Ingest a folder into the store (accumulates).")
    s_add.add_argument("directory", help="Directory of exported thread files.")
    s_add.add_argument("--db", default="arc.db", help="Store database path (default: arc.db).")
    s_add.add_argument("--pattern", default=None,
                       help="Glob for input files (default: all of *.txt, *.eml, *.mbox).")
    s_add.add_argument("--recursive", action="store_true", help="Recurse into subfolders.")
    s_add.set_defaults(func=cmd_store)

    s_stats = store_sub.add_parser("stats", help="Show what the store currently holds.")
    s_stats.add_argument("--db", default="arc.db", help="Store database path (default: arc.db).")
    s_stats.set_defaults(func=cmd_store)

    s_dd = store_sub.add_parser("dedup", help="Branch-aware dedup across every file in the store.")
    s_dd.add_argument("--db", default="arc.db", help="Store database path (default: arc.db).")
    s_dd.set_defaults(func=cmd_store)

    s_tl = store_sub.add_parser("timeline", help="Render a timeline from everything in the store.")
    s_tl.add_argument("-o", "--output", required=True, help="Output HTML file path.")
    s_tl.add_argument("--db", default="arc.db", help="Store database path (default: arc.db).")
    s_tl.add_argument("--title", default=None, help="Override the page title.")
    s_tl.add_argument("--link-base", default=None,
                      help="Rewrite source links to this base URL instead of local file:// paths.")
    s_tl.set_defaults(func=cmd_store)

    p_tl = sub.add_parser(
        "timeline", help="Render events.json into a self-contained tabbed HTML timeline."
    )
    p_tl.add_argument("events", help="Path to a JSON array of event objects.")
    p_tl.add_argument("-o", "--output", required=True, help="Output HTML file path.")
    p_tl.add_argument(
        "--title", default=None, help="Override the page title (defaults to the JSON's own title)."
    )
    p_tl.set_defaults(func=cmd_timeline)

    p_tt = sub.add_parser(
        "timeline-threads",
        help="Build a timeline straight from a folder of exported email threads (dedup-aware).",
    )
    p_tt.add_argument("directory", help="Directory of exported thread files.")
    p_tt.add_argument("-o", "--output", required=True, help="Output HTML file path.")
    p_tt.add_argument(
        "--pattern", default=None,
        help="Glob for input files (default: all of *.txt, *.eml, *.mbox)."
    )
    p_tt.add_argument("--title", default=None, help="Override the page title.")
    p_tt.add_argument(
        "--link-base", default=None,
        help="Rewrite each card's source link to this base URL (e.g. a SharePoint/Drive "
             "folder) instead of a local file:// path.",
    )
    p_tt.set_defaults(func=cmd_timeline_threads)

    p_in = sub.add_parser(
        "ingest",
        help="Turn a folder of email threads into an editable draft timeline-data JSON "
             "(scaffold to refine, then render with `timeline`).",
    )
    p_in.add_argument(
        "directory", help="Directory of exported thread files (subfolders become tabs)."
    )
    p_in.add_argument("-o", "--output", required=True, help="Output draft JSON path.")
    p_in.add_argument("--pattern", default=None,
                      help="Glob for input files (default: all of *.txt, *.eml, *.mbox).")
    p_in.add_argument("--title", default=None, help="Page title for the draft.")
    p_in.add_argument(
        "--link-base", default=None,
        help="Rewrite source links to this base URL instead of local file:// paths.",
    )
    p_in.set_defaults(func=cmd_ingest)

    p_org = sub.add_parser(
        "organize",
        help="AI-organize a folder of emails into categories and render the timeline "
             "(opt-in; needs ANTHROPIC_API_KEY).",
    )
    p_org.add_argument("directory", help="Directory of exported emails (searched recursively).")
    p_org.add_argument("-o", "--output", required=True, help="Output HTML file path.")
    p_org.add_argument("--draft", default=None, help="Also write the editable draft JSON here.")
    p_org.add_argument("--pattern", default=None,
                       help="Glob for input files (default: all of *.txt, *.eml, *.mbox).")
    p_org.add_argument("--title", default=None, help="Override the page title.")
    p_org.add_argument("--model", default="claude-opus-4-8", help="Claude model to use.")
    p_org.add_argument(
        "--link-base", default=None,
        help="Rewrite source links to this base URL instead of local file:// paths.",
    )
    p_org.set_defaults(func=cmd_organize)

    p_web = sub.add_parser(
        "web",
        help="Launch a thin local web UI: drag-drop an export, see keep/delete, "
             "pick threads, browse the timeline (stdlib only; local & offline).",
    )
    p_web.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1).")
    p_web.add_argument("--port", type=int, default=8000, help="Port (default: 8000).")
    p_web.add_argument("--no-browser", action="store_true",
                       help="Do not auto-open a browser window.")
    p_web.set_defaults(func=cmd_web)

    return parser


def _make_stdout_safe() -> None:
    """Never let a Unicode subject/title crash output on a cp1252 console.

    Subjects and titles can carry arrows/ellipses/emoji; a Windows console in
    cp1252 would raise ``UnicodeEncodeError`` when one is printed. Switching the
    streams to ``backslashreplace`` keeps ASCII output identical and degrades the
    rare unencodable glyph to an escape instead of aborting the command. (No-op
    when stdout is a plain buffer, e.g. captured in tests.)
    """
    import sys as _sys

    for stream in (_sys.stdout, _sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _make_stdout_safe()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
