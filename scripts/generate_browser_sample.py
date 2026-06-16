#!/usr/bin/env python3
"""Generate docs/sample-threads.js — the one-click "Load the sample data" set
for the in-browser dedup tool (docs/try.html).

The browser port (docs/arc-dedup.js) parses the plain-text stacked export format
only — it does not read `.eml`/`.mbox` (those need Python's stdlib email/mailbox)
— so this sample is `.txt`-only. It is a curated, coherent slice of the same
synthetic Voltera conversations as examples/archive/, chosen so the in-page
verdict shows the interesting cases the JS port supports:

* branch-aware keeps and strict-subset redundancies;
* a three-way branch where no single export is a superset of the others;
* attachment branching — two files sharing their messages but carrying different
  attachments are both kept (attachments are first-class keys, matched by name);
* normalization collapse — the same message re-exported with a quoted-reply tail
  or a `-- ` signature folds back onto the plain thread.

Run:  python scripts/generate_browser_sample.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_example_archive import M  # noqa: E402  (canonical message table)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "sample-threads.js")


def _block(key, body=None, attachments=None):
    sender, recipient, subject, date, canon = M[key]
    text = canon if body is None else body
    lines = ["From: %s" % sender, "Sent: %s" % date,
             "To: %s" % recipient, "Subject: %s" % subject]
    if attachments:
        lines.append("Attachments: %s" % ", ".join(attachments))
    lines += ["", text, ""]
    return "\n".join(lines)


def thread(name, keys, attachments_on_last=None):
    """A stacked .txt export of several messages (newest first)."""
    atts = {keys[-1]: attachments_on_last} if attachments_on_last else {}
    blocks = [_block(k, attachments=atts.get(k)) for k in reversed(keys)]
    return {"name": name, "content": "\n".join(blocks).rstrip() + "\n"}


def single(name, key, body=None, attachments=None):
    """A one-message export (optionally with an overridden body / attachments)."""
    return {"name": name, "content": _block(key, body=body, attachments=attachments).rstrip() + "\n"}


def build_sample():
    q2 = M["c12_normalize_m2"][4]
    q1 = M["c12_normalize_m1"][4]
    quoted_body = (q2 + "\n\nOn Sat, 22 Nov 2025 09:00:00 -0800, "
                   "Sofia Marenko <sofia.marenko@voltera.example> wrote:\n> " + q1)
    signed_body = M["c12_normalize_m1"][4] + "\n\n-- \nSofia Marenko\nPerception Lead, Voltera"

    K = lambda slug, n: ["%s_m%d" % (slug, i) for i in range(n)]  # noqa: E731
    p = K("c01_perception", 4)
    r = K("c03_runbook", 4)
    loc = K("c05_localization", 4)
    tw = K("c11_threeway", 5)
    a = K("c13_assets", 2)
    nz = K("c12_normalize", 3)

    return [
        # Conversation 1 — a full thread, a partial subset, and a forward whose
        # only unique content is a PDF (kept).
        thread("perception_signoff_full.txt", p),
        thread("perception_signoff_early.txt", p[0:2]),
        single("perception_signoff_forward.txt", p[3],
               attachments=["c01_perception_eval.pdf"]),

        # Conversation 2 — a full thread and two strict subsets.
        thread("rollout_runbook_full.txt", r),
        thread("rollout_runbook_mid.txt", r[1:3]),
        single("rollout_runbook_open.txt", r[0]),

        # Conversation 3 — a three-way branch: none is a superset of the others.
        thread("lanechange_branch_perception.txt", [tw[0], tw[1], tw[2]]),
        thread("lanechange_branch_regulatory.txt", [tw[0], tw[1], tw[3]]),
        thread("lanechange_branch_validation.txt", [tw[0], tw[1], tw[4]]),
        thread("lanechange_open.txt", tw[0:2]),

        # Conversation 4 — attachment branching: two files share their messages
        # but carry different attachments, so both are kept; the plain copy is a
        # subset of the first.
        thread("trip_assets_v1.txt", a, attachments_on_last=["spec_v1.pdf", "ride_metrics.csv"]),
        single("trip_assets_v2.txt", a[1], attachments=["spec_v2.pdf", "screen_mock.png"]),
        thread("trip_assets_plain.txt", a),

        # Conversation 5 — normalization collapse: a quoted-reply tail and a
        # signature both fold back onto the plain thread.
        thread("metrics_gonogo_full.txt", nz),
        single("metrics_gonogo_quoted.txt", nz[2], body=quoted_body),
        single("metrics_gonogo_signed.txt", nz[1], body=signed_body),

        # Conversation 6 — another full thread plus subsets, for volume.
        thread("localization_handoff_full.txt", loc),
        thread("localization_handoff_early.txt", loc[0:2]),
        single("localization_handoff_open.txt", loc[0]),
    ]


_HEADER = """\
/*!
 * sample-threads.js - synthetic demo data for the in-browser dedup tool.
 *
 * A curated, .txt-only slice of the fictional "Voltera / Drive Assist 3.0"
 * conversations (see examples/archive/), so the live page's one-click "Load the
 * sample data" button shows the branch-aware dedup at work - branches vs.
 * strict subsets, a three-way fork, attachment branching, and quoted-tail /
 * signature collapse. The browser port parses the plain-text format only, so
 * this stays .txt. All content is fully synthetic.
 *
 * GENERATED by scripts/generate_browser_sample.py - do not edit by hand.
 *
 * Exposes window.SAMPLE_THREADS (browser) / module.exports (Node) as an array
 * of {name, content} records - the same shape the file picker produces.
 */
(function (global) {
  "use strict";

  var SAMPLE_THREADS = [
"""

_FOOTER = """\
  ];

  if (typeof module !== "undefined" && module.exports) {
    module.exports = SAMPLE_THREADS;
  } else {
    global.SAMPLE_THREADS = SAMPLE_THREADS;
  }
})(typeof self !== "undefined" ? self : this);
"""


def main():
    records = build_sample()
    parts = []
    for rec in records:
        parts.append("    { name: %s, content: %s }"
                     % (json.dumps(rec["name"]), json.dumps(rec["content"])))
    body = ",\n".join(parts) + "\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_HEADER + body + _FOOTER)
    print("Wrote %d sample thread(s) to %s" % (len(records), OUT))


if __name__ == "__main__":
    main()
