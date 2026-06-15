"""Thin local web UI for the Archive Reconstruction Platform (roadmap item 5).

Drag-drop an export in the browser, see the branch-aware keep/delete call,
hand-pick the threads you care about, and browse a timeline of just those.

Standard library only — a small :mod:`http.server` handler, **no Flask/FastAPI**,
so the toolkit's zero-dependency property holds even for the UI layer. The
server writes the dropped files into a temporary working directory and then
reuses the *exact* folder pipeline the CLI already uses
(:func:`arc.dedup.dedup_directory`, :func:`arc.bridge.collect_unique_messages`,
:func:`arc.bridge.timeline_data_from_messages`, :func:`arc.timeline.render_timeline`).
No dedup or timeline logic is re-implemented here.

It binds to localhost, makes no outbound connection, and — like the rest of the
toolkit — only ever *recommends* a delete set. It never deletes anything.

Why not multipart uploads? The stdlib ``cgi`` module (the usual way to parse
``multipart/form-data``) was removed in Python 3.13. Every input format here is
text (``.txt`` / ``.eml`` / ``.mbox``), so the browser reads each dropped file
as text and POSTs a small JSON payload instead — no third-party parser needed.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

from .bridge import collect_unique_messages, timeline_data_from_messages
from .dedup import analyze, content_keys
from .parse import SUPPORTED_EXTS, find_message_files, parse_path
from .timeline import count_events, render_timeline

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(name: str) -> str:
    """Reduce an uploaded filename to a bare, path-free basename."""
    base = os.path.basename((name or "").replace("\\", "/"))
    base = _SAFE_NAME_RE.sub("_", base).strip("._") or "upload"
    return base


class Session:
    """The single working set behind the UI: a temp folder of dropped files
    plus the most recently rendered timeline. A local tool is single-user, so
    one shared session (guarded by a lock) is all we need."""

    def __init__(self) -> None:
        self.dir = tempfile.mkdtemp(prefix="arc-web-")
        self.lock = threading.Lock()
        self.timeline_html: Optional[str] = None

    # -- mutations ------------------------------------------------------- #
    def save_uploads(self, files: List[Dict[str, str]]) -> Tuple[int, List[str]]:
        """Write uploaded ``{name, content}`` records into the working dir.

        Returns ``(saved_count, skipped_names)``; unsupported extensions are
        skipped so the folder pipeline only ever sees files it understands.
        """
        saved = 0
        skipped: List[str] = []
        for f in files:
            name = _safe_name(f.get("name", ""))
            ext = os.path.splitext(name)[1].lower()
            if ext not in SUPPORTED_EXTS:
                skipped.append(f.get("name", name))
                continue
            with open(os.path.join(self.dir, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(f.get("content", ""))
            saved += 1
        return saved, skipped

    def reset(self) -> None:
        for entry in os.listdir(self.dir):
            try:
                os.remove(os.path.join(self.dir, entry))
            except OSError:
                pass
        self.timeline_html = None

    # -- reads ----------------------------------------------------------- #
    def state(self) -> Dict[str, Any]:
        """Per-file dedup verdict + counts, plus a headline summary."""
        paths = find_message_files(self.dir)
        file_keys = []
        info_by_name: Dict[str, Dict[str, Any]] = {}
        for p in paths:
            name = os.path.basename(p)
            msgs = parse_path(p)
            keys = content_keys(msgs)
            atts = sorted({a.strip() for m in msgs for a in m.attachments if a.strip()})
            file_keys.append((name, keys))
            info_by_name[name] = {
                "name": name,
                "messages": len(msgs),
                "attachments": atts,
            }

        result = analyze(file_keys)
        keep_set = set(result.keep)
        files: List[Dict[str, Any]] = []
        for r in result.reports:
            info = info_by_name.get(r.name, {"name": r.name, "messages": 0, "attachments": []})
            covered_by = [n for n in r.superseded_by if n in keep_set] or list(r.superseded_by)
            info.update({"redundant": r.redundant, "coveredBy": covered_by})
            files.append(info)

        uniques, total = collect_unique_messages(paths)
        return {
            "files": files,
            "summary": {
                "files": len(result.reports),
                "kept": len(result.keep),
                "redundant": len(result.delete),
                "uniqueMessages": len(uniques),
                "duplicates": max(0, total - len(uniques)),
            },
        }

    def build_timeline(self, selected: List[str]) -> Dict[str, Any]:
        """Render a timeline from just the selected files; store the HTML."""
        chosen = set(selected)
        paths = [p for p in find_message_files(self.dir) if os.path.basename(p) in chosen]
        if not paths:
            self.timeline_html = None
            return {"ok": False, "error": "No threads selected."}

        uniques, total = collect_unique_messages(paths)
        duplicates = max(0, total - len(uniques))
        subtitle = ("%d selected file(s); %d unique message(s) after dedup "
                    "(%d duplicate%s collapsed)."
                    % (len(paths), len(uniques), duplicates, "" if duplicates == 1 else "s"))
        data = timeline_data_from_messages(
            uniques, total=total, title="Selected threads",
            directory=self.dir, label="Conversations", subtitle=subtitle,
        )
        self.timeline_html = render_timeline(data)
        return {"ok": True, "count": count_events(data), "subtitle": subtitle}


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #
_PLACEHOLDER = (
    "<!doctype html><meta charset='utf-8'>"
    "<body style='margin:0;font:15px/1.6 system-ui,sans-serif;color:#64748b;"
    "display:flex;align-items:center;justify-content:center;height:100vh;"
    "background:#f8fafc;text-align:center;padding:2rem'>"
    "<div>Select one or more threads on the left, then "
    "<b>Build&nbsp;timeline</b> to preview the conversation here.</div></body>"
)


class _Handler(BaseHTTPRequestHandler):
    server_version = "ETT-web"
    session: Session  # set on the server instance below

    # quieter, single-line logging
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, code: int = 200) -> None:
        self._send(code, html.encode("utf-8"), "text/html; charset=utf-8")

    def _send_json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}

    # -- routes ---------------------------------------------------------- #
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        sess = self.server.session  # type: ignore[attr-defined]
        if path == "/":
            self._send_html(PAGE_HTML)
        elif path == "/timeline":
            self._send_html(sess.timeline_html or _PLACEHOLDER)
        elif path == "/api/state":
            with sess.lock:
                self._send_json(sess.state())
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        sess = self.server.session  # type: ignore[attr-defined]
        payload = self._read_json()
        if path == "/api/upload":
            with sess.lock:
                saved, skipped = sess.save_uploads(payload.get("files", []) or [])
                state = sess.state()
            state["saved"] = saved
            state["skipped"] = skipped
            self._send_json(state)
        elif path == "/api/build":
            with sess.lock:
                self._send_json(sess.build_timeline(payload.get("selected", []) or []))
        elif path == "/api/reset":
            with sess.lock:
                sess.reset()
                self._send_json(sess.state())
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")


def run_server(host: str = "127.0.0.1", port: int = 8000,
               open_browser: bool = False) -> ThreadingHTTPServer:
    """Start the UI server. Returns the (already-serving) server in a daemon
    thread; the caller decides how long to keep it alive."""
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.session = Session()  # type: ignore[attr-defined]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    if open_browser:
        import webbrowser
        webbrowser.open("http://%s:%d/" % (host, port))
    return httpd


def serve(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> int:
    """Blocking entry point used by ``arc web`` — serve until Ctrl-C."""
    httpd = run_server(host, port, open_browser=open_browser)
    url = "http://%s:%d/" % (host, port)
    print("Archive Reconstruction Platform - local web UI")
    print("  Serving at %s  (local only, no data leaves this machine)" % url)
    print("  Working dir: %s" % httpd.session.dir)  # type: ignore[attr-defined]
    print("  Press Ctrl-C to stop.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        httpd.shutdown()
    return 0


# --------------------------------------------------------------------------- #
# The single-page app (self-contained: inline CSS + vanilla JS, no CDN)
# --------------------------------------------------------------------------- #
PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archive Reconstruction Platform</title>
<style>
  :root{
    --bg:#f1f5f9; --panel:#ffffff; --ink:#0f172a; --muted:#64748b;
    --line:#e2e8f0; --accent:#1e88e5; --keep:#16a34a; --redundant:#94a3b8;
    --radius:12px; --shadow:0 1px 3px rgba(15,23,42,.08),0 4px 16px rgba(15,23,42,.05);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  header{padding:20px 28px;background:var(--panel);border-bottom:1px solid var(--line);
    display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
  header h1{font-size:19px;margin:0;letter-spacing:-.01em}
  header .sub{color:var(--muted);font-size:13px}
  .pill{margin-left:auto;font-size:11px;font-weight:600;color:#0369a1;
    background:#e0f2fe;border:1px solid #bae6fd;border-radius:999px;padding:3px 10px}
  main{padding:24px 28px;max-width:1280px;margin:0 auto}
  .drop{border:2px dashed #cbd5e1;border-radius:var(--radius);background:var(--panel);
    padding:34px;text-align:center;color:var(--muted);transition:.15s;cursor:pointer}
  .drop.hover{border-color:var(--accent);background:#eff6ff;color:var(--accent)}
  .drop b{color:var(--ink)}
  .drop .hint{font-size:12.5px;margin-top:6px}
  input[type=file]{display:none}
  .grid{display:grid;grid-template-columns:minmax(340px,420px) 1fr;gap:22px;margin-top:22px;
    align-items:start}
  @media(max-width:900px){.grid{grid-template-columns:1fr}}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
    box-shadow:var(--shadow);overflow:hidden}
  .card>h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
    margin:0;padding:14px 16px;border-bottom:1px solid var(--line)}
  .chips{display:flex;gap:8px;flex-wrap:wrap;padding:14px 16px;border-bottom:1px solid var(--line)}
  .chip{font-size:12.5px;font-weight:600;background:#f8fafc;border:1px solid var(--line);
    border-radius:999px;padding:4px 11px;color:var(--ink)}
  .chip.keep{color:var(--keep);border-color:#bbf7d0;background:#f0fdf4}
  .chip.del{color:#b45309;border-color:#fde68a;background:#fffbeb}
  .toolbar{display:flex;gap:8px;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid var(--line)}
  button{font:inherit;font-size:13px;border:1px solid var(--line);background:#fff;color:var(--ink);
    border-radius:8px;padding:7px 12px;cursor:pointer;transition:.12s}
  button:hover{border-color:#cbd5e1;background:#f8fafc}
  button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
  button.primary:hover{background:#1976d2}
  button:disabled{opacity:.5;cursor:not-allowed}
  ul.files{list-style:none;margin:0;padding:6px;max-height:62vh;overflow:auto}
  li.file{display:flex;gap:11px;align-items:flex-start;padding:11px 12px;border-radius:9px}
  li.file:hover{background:#f8fafc}
  li.file input{margin-top:3px;width:16px;height:16px;accent-color:var(--accent)}
  .fmeta{flex:1;min-width:0}
  .fname{font-weight:600;word-break:break-all}
  .fsub{font-size:12.5px;color:var(--muted);margin-top:2px}
  .badge{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;
    border-radius:6px;padding:2px 7px;white-space:nowrap}
  .badge.keep{color:#fff;background:var(--keep)}
  .badge.del{color:#475569;background:#e2e8f0}
  .att{display:inline-block;font-size:11.5px;color:#7c3aed;background:#f5f3ff;
    border:1px solid #ddd6fe;border-radius:6px;padding:1px 7px;margin:3px 4px 0 0}
  .empty{padding:40px 16px;text-align:center;color:var(--muted)}
  .framewrap{height:78vh;min-height:480px}
  iframe{width:100%;height:100%;border:0;border-radius:0 0 var(--radius) var(--radius);background:#fff}
  .note{color:var(--muted);font-size:12.5px;margin-top:16px;text-align:center}
  .buildbar{display:flex;align-items:center;gap:12px;padding:12px 16px;border-bottom:1px solid var(--line)}
  .buildbar .status{font-size:12.5px;color:var(--muted)}
</style>
</head>
<body>
<header>
  <h1>Archive&nbsp;Reconstruction&nbsp;Platform</h1>
  <span class="sub">Branch-aware dedup &amp; timeline &mdash; drag in an export, keep the branches that matter.</span>
  <span class="pill">local &middot; offline</span>
</header>
<main>
  <label class="drop" id="drop">
    <div><b>Drag &amp; drop</b> your exported email files here, or click to browse.</div>
    <div class="hint">Supports .txt, .eml and .mbox &mdash; nothing is uploaded anywhere; it stays on this machine.</div>
    <input type="file" id="picker" multiple accept=".txt,.eml,.mbox">
  </label>

  <section class="grid" id="workspace" style="display:none">
    <div class="card">
      <h2>Files &amp; dedup verdict</h2>
      <div class="chips" id="chips"></div>
      <div class="toolbar">
        <button id="selKeep" class="primary">Select keepers</button>
        <button id="selAll">Select all</button>
        <button id="selNone">Clear selection</button>
        <button id="reset" style="margin-left:auto">Remove all files</button>
      </div>
      <ul class="files" id="fileList"></ul>
    </div>

    <div class="card">
      <h2>Timeline preview</h2>
      <div class="buildbar">
        <button id="build" class="primary">Build timeline from selected</button>
        <span class="status" id="buildStatus"></span>
      </div>
      <div class="framewrap"><iframe id="frame" src="/timeline" title="Timeline preview"></iframe></div>
    </div>
  </section>

  <p class="note">The tool only <b>recommends</b> which files are redundant &mdash; it never deletes anything.
  Keepers are the branches that, together, preserve every message and attachment.</p>
</main>

<script>
(function(){
  "use strict";
  var drop = document.getElementById("drop");
  var picker = document.getElementById("picker");
  var workspace = document.getElementById("workspace");
  var chips = document.getElementById("chips");
  var fileList = document.getElementById("fileList");
  var buildStatus = document.getElementById("buildStatus");
  var frame = document.getElementById("frame");

  function readFile(file){
    return new Promise(function(resolve){
      var r = new FileReader();
      r.onload = function(){ resolve({name:file.name, content:String(r.result||"")}); };
      r.onerror = function(){ resolve({name:file.name, content:""}); };
      r.readAsText(file);
    });
  }

  function postJSON(url, body){
    return fetch(url, {method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify(body||{})}).then(function(r){ return r.json(); });
  }

  function upload(fileObjs){
    if(!fileObjs.length) return;
    Promise.all(Array.prototype.map.call(fileObjs, readFile)).then(function(files){
      return postJSON("/api/upload", {files:files});
    }).then(function(state){
      if(state.skipped && state.skipped.length){
        buildStatus.textContent = "Skipped (unsupported): " + state.skipped.join(", ");
      }
      render(state);
    });
  }

  function chip(text, cls){
    var s = document.createElement("span");
    s.className = "chip" + (cls?(" "+cls):"");
    s.textContent = text;
    return s;
  }

  function render(state){
    var files = state.files || [];
    if(!files.length){
      workspace.style.display = "none";
      return;
    }
    workspace.style.display = "";
    var s = state.summary || {};
    chips.innerHTML = "";
    chips.appendChild(chip(s.files + " file(s)"));
    chips.appendChild(chip(s.kept + " to keep", "keep"));
    chips.appendChild(chip(s.redundant + " redundant", "del"));
    chips.appendChild(chip(s.uniqueMessages + " unique message(s)"));

    fileList.innerHTML = "";
    files.forEach(function(f){
      var li = document.createElement("li");
      li.className = "file";

      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = f.name;
      cb.checked = !f.redundant;          // preselect the keepers
      cb.dataset.redundant = f.redundant ? "1" : "0";

      var meta = document.createElement("div");
      meta.className = "fmeta";
      var nm = document.createElement("div");
      nm.className = "fname";
      nm.textContent = f.name;
      var badge = document.createElement("span");
      badge.className = "badge " + (f.redundant ? "del" : "keep");
      badge.textContent = f.redundant ? "redundant" : "keep";
      badge.style.marginLeft = "8px";
      nm.appendChild(badge);

      var sub = document.createElement("div");
      sub.className = "fsub";
      var bits = [f.messages + " message(s)"];
      if(f.redundant && f.coveredBy && f.coveredBy.length){
        bits.push("subset of " + f.coveredBy.join(", "));
      }
      sub.textContent = bits.join(" · ");

      meta.appendChild(nm);
      meta.appendChild(sub);
      (f.attachments||[]).forEach(function(a){
        var t = document.createElement("span");
        t.className = "att"; t.textContent = a;
        meta.appendChild(t);
      });

      li.appendChild(cb);
      li.appendChild(meta);
      fileList.appendChild(li);
    });
  }

  function checkboxes(){ return fileList.querySelectorAll("input[type=checkbox]"); }
  function setAll(pred){
    checkboxes().forEach(function(cb){ cb.checked = pred(cb); });
  }

  document.getElementById("selKeep").onclick = function(){ setAll(function(cb){ return cb.dataset.redundant !== "1"; }); };
  document.getElementById("selAll").onclick  = function(){ setAll(function(){ return true; }); };
  document.getElementById("selNone").onclick = function(){ setAll(function(){ return false; }); };
  document.getElementById("reset").onclick = function(){
    postJSON("/api/reset", {}).then(render);
    frame.src = "/timeline?ts=" + Date.now();
    buildStatus.textContent = "";
  };

  document.getElementById("build").onclick = function(){
    var selected = [];
    checkboxes().forEach(function(cb){ if(cb.checked) selected.push(cb.value); });
    if(!selected.length){ buildStatus.textContent = "Select at least one thread."; return; }
    buildStatus.textContent = "Building…";
    postJSON("/api/build", {selected:selected}).then(function(res){
      if(res.ok){
        buildStatus.textContent = res.count + " event(s) · " + res.subtitle;
        frame.src = "/timeline?ts=" + Date.now();
      } else {
        buildStatus.textContent = res.error || "Nothing to show.";
      }
    });
  };

  // Drag & drop + click-to-browse
  ["dragenter","dragover"].forEach(function(ev){
    drop.addEventListener(ev, function(e){ e.preventDefault(); drop.classList.add("hover"); });
  });
  ["dragleave","drop"].forEach(function(ev){
    drop.addEventListener(ev, function(e){ e.preventDefault(); drop.classList.remove("hover"); });
  });
  drop.addEventListener("drop", function(e){
    if(e.dataTransfer && e.dataTransfer.files) upload(e.dataTransfer.files);
  });
  picker.addEventListener("change", function(){ upload(picker.files); picker.value = ""; });

  // Restore any existing working set on load.
  fetch("/api/state").then(function(r){ return r.json(); }).then(render);
})();
</script>
</body>
</html>
"""
