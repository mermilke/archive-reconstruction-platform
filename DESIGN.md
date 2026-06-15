# Design — branch-aware deduplication

## The problem

You archive a mailbox, or you save a conversation one message at a time, and you
end up with a folder of exported thread files. Many of them overlap heavily:
the same conversation, captured at different moments, by different people, in
different time zones. Some files are pure duplicates. Some look like duplicates
but secretly carry a reply, or an attachment, that no other file has.

You want to delete the redundant ones **without losing a single message or
attachment**. Doing that by hand does not scale, and the obvious shortcuts are
wrong.

## The naive approach (and why it breaks)

The tempting heuristic: *"keep the biggest file in each group; it must contain
all the others."*

This fails the moment a thread **forks**. Picture a conversation that splits:

```
            R1  (open)
            R2  (reply)
           /      \
   A3 (long       B3 (forward with
   discussion)     a unique attachment)
   A4 ...
```

- File **A** captures `R1, R2, A3, A4` — the long discussion branch.
- File **B** captures `R1, R2, B3` plus an attachment `budget.xlsx` that A
  never had.

A is bigger (more messages, more bytes). But A is **not** a superset of B: it is
missing `B3` and `budget.xlsx`. Delete B because it is smaller and you silently
lose an attachment. Size, byte-equality, and "newest file wins" all make this
mistake. The fork is exactly where they fail.

## The content-key model

Instead of comparing files as blobs, reduce each file to a **set of content
keys** and compare the *sets*:

- **message key** = `("msg", normalized_sender, body_fingerprint)`
  - sender is normalized to its email address (or lowercased name).
  - body fingerprint first strips quoted prior messages (`On <date>, <person>
    wrote:` attribution, `-----Original Message-----` forwards, `>`-quoted
    lines) and a trailing `-- ` signature (see `src/arc/normalize.py`), then
    collapses whitespace and lowercases the text. So the same reply fingerprints
    identically whether an export pasted a quote-tail or signature onto it, and
    trivial reflow does not split one message into two. The full body is still
    kept on the `Message` for display — only the identity fingerprint is cleaned.
  - **timestamps are deliberately excluded.** The same message is frequently
    re-rendered with a different `Sent:`/`Date:` value across exports — most
    often because of time-zone differences. Including the timestamp would make
    one message look like two and defeat the whole exercise.
- **attachment key** = `("att", "", normalized_name)`
  - attachments are **first-class content**. A forward whose only unique
    contribution is an attachment must never be judged redundant.

A file's key-set is the union of all its message keys and attachment keys.

## The decision rule

> A file is **redundant** if and only if its key-set is a **subset** of another
> file's key-set.

- Files that are a subset of nothing are the **branches**. Keeping all of them
  preserves every message and every attachment by construction — their union is
  the union of everything.
- Strict subsets are safe to delete: every key they contain lives on in a
  branch.

### Tie-break for identical content

Two files with *equal* key-sets are subsets of each other. Collapsing both would
be wrong (you'd lose the content); keeping both is redundant. The rule: keep one
deterministically (the lexicographically smaller filename) and flag the rest.
This guarantees an identical-content pair collapses to exactly one keeper.

## Worked example (the synthetic fixtures)

`examples/threads/` encodes exactly the fork above — an internal email thread
about a (fictional) "Drive Assist 3.0" software rollout:

| File                            | Keys                                      | Verdict |
|---------------------------------|-------------------------------------------|---------|
| `thread_main_full.txt`          | R1, R2, A3, A4, att:rollout_runbook.pdf   | keep (branch) |
| `thread_forward_attachment.txt` | R1, R2, B3, att:safety_case_final.pdf     | keep (branch) |
| `thread_partial_mid.txt`        | R1, R2, A3                                | delete (⊆ full) |
| `thread_partial_early.txt`      | R1, R2                                    | delete (⊆ both) |
| `thread_forward_noattach.txt`   | R1, R2, B3 *(no attachment)*              | delete (⊆ forward) |
| `thread_single_open.txt`        | R1                                        | delete (⊆ both) |

Two details the fixtures are built to prove:

- `thread_partial_early.txt` stores `R1`/`R2` with **time-zone-shifted**
  timestamps (and uses `Date:` instead of `Sent:`). It still dedups cleanly —
  evidence that timestamps are ignored.
- `thread_forward_noattach.txt` has B3's message text but **drops the
  attachment header**, so it becomes a subset of the forward branch. The
  attachment is precisely what keeps `thread_forward_attachment.txt` alive as a
  branch.

## Verifying dedup against the real conversation (item 3)

Content-key dedup is robust, but on its own it is an *argument from overlap*: it
says "this file's content is contained in that one." When an export preserves
RFC 5322 threading headers — `Message-ID` / `In-Reply-To` / `References`, which
real `.eml`/`.mbox` always do — we can turn that argument into a check.

`arc.thread` rebuilds the genuine reply **forest**: each message links to its
parent via `In-Reply-To` (preferred) or the last resolvable `References` entry;
messages with no known parent are roots. When no threading headers are present
(e.g. the plain-text examples), identity falls back to the content key and every
unique message is its own root — the tree degrades gracefully.

The payoff is verification. Identity is the authoritative `Message-ID` where
present, else the content key. We take dedup's keep-set and confirm **every**
message identity in the whole corpus still lives in some kept branch. If it
does, the collapse is provably non-lossy — reported as

> Collapsed 3 files -> 2 branches; 5 unique messages, 0 lost.

If a content-only collapse would ever drop a message that the headers prove is
distinct, `verify_no_loss` lists it instead of silently trusting the heuristic.
`arc tree <dir>` prints the forest and this benchmark together.

## The local web UI (item 5)

The web UI exists to make the keep/delete call tangible: drag an export into the
browser, see which files are branches and which are redundant subsets, tick the
threads you want, and preview a timeline of just those. The design constraint
was to add it **without compromising the two things that define the project** —
zero dependencies and a single source of truth for dedup.

- **No framework.** The roadmap *allowed* a light framework here, but the UI
  runs on the stdlib `http.server` alone, so the toolkit still installs with
  zero `pip` dependencies. `arc.web` is one small request handler plus a
  self-contained HTML page (inline CSS/JS, no CDN).
- **One dedup implementation, not two.** The server never re-derives a verdict.
  It writes the dropped files into a temporary working directory and calls the
  exact folder pipeline the CLI uses (`dedup_directory`,
  `collect_unique_messages`, `timeline_data_from_messages`, `render_timeline`).
  The web answer equals `arc dedup` by construction, and `tests/test_web.py`
  pins that equality.
- **JSON upload, not multipart.** Python 3.13 removed the stdlib `cgi` module
  (the usual `multipart/form-data` parser), and every input format here is text.
  So the browser reads each file with `FileReader` and POSTs a small JSON body —
  no third-party parser, no binary handling.
- **Local and recommend-only, like the rest.** It binds to `127.0.0.1`, makes no
  outbound request, and still only proposes a delete set. Nothing is deleted, and
  the working directory is a throwaway temp folder.

## Limits (known, and deliberately so for v1)

- **Body fingerprinting is exact** (after normalization). As of roadmap item 2
  the fingerprint strips quoted reply chains, `-----Original Message-----`
  forwards, `On <date>, <person> wrote:` framing, and `-- ` signatures before
  comparing, with messy fixtures and edge-case tests pinning the behavior
  (`tests/fixtures/messy/`, `tests/test_parse_hardening.py`). The remaining
  exactness limit: two genuinely different paraphrases of the same point still
  fingerprint differently — semantic dedup is out of scope by design.
- **Message-boundary detection is format-specific.** The parser expects the
  documented stacked, newest-first export shape, and now tolerates malformed
  blocks (missing blank line between headers and body) and folded header
  continuation lines. `.eml`/`.mbox` ingestion (roadmap item 1) sidesteps text
  boundary-guessing entirely, and `References`/`In-Reply-To` reconstruction
  (item 3, above) verifies the result against the real reply structure.
- **Attachment identity is by name only.** Two different files sharing a name
  collide; the same file under two names looks distinct. Content hashing is a
  future refinement.
- The tool **only recommends.** It never deletes. That is a feature, not a
  limitation: a wrong call costs a recommendation, not your data.
