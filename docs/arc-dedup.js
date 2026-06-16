/*!
 * arc-dedup.js — branch-aware email-thread deduplication, in the browser.
 *
 * A faithful JavaScript port of the Python core: the message/attachment
 * content-key model from src/arc/dedup.py, the body normalization from
 * src/arc/normalize.py, the thread parser from src/arc/parse.py, and the
 * message-dedup half of src/arc/bridge.py (collect_unique_messages).
 *
 * It runs entirely client-side so the web demo needs no server and no upload —
 * the dropped files never leave the browser.
 *
 * The crown-jewel idea is unchanged: reduce each file to a SET OF CONTENT KEYS
 * (one per message = sender + a fingerprint of the body, timestamps ignored;
 * one per attachment name). A file is REDUNDANT only when its key-set is a
 * subset of another file's; files that are a subset of nothing are the BRANCHES
 * worth keeping.
 *
 * Parity with the Python implementation is enforced by tests/test_js_parity.py,
 * which runs this module (via tests/js-parity-driver.js) over examples/threads
 * and asserts the keep/delete verdict matches `arc dedup`. If you change the
 * algorithm here, change it in Python too — the test will catch drift.
 *
 * Dual-mode: exposes window.ArcDedup in the browser and module.exports in Node.
 */
(function (global) {
  "use strict";

  // -- line splitting: mimic Python str.splitlines() (no trailing-newline tail)
  function splitlines(s) {
    if (s === "" || s == null) return [];
    s = String(s);
    var parts = s.split(/\r\n|\r|\n/);
    if (parts.length && parts[parts.length - 1] === "" && /[\r\n]$/.test(s)) {
      parts.pop();
    }
    return parts;
  }

  // =======================================================================
  // parse.py — exported thread text -> message objects
  // =======================================================================
  // A header line is "Word: value" where Word may contain hyphens (Reply-To).
  var HEADER_RE = /^([A-Za-z][A-Za-z\-]*):\s*(.*)$/;

  function parseThread(text) {
    var lines = splitlines(text);

    // A new message boundary is a "From:" header at the start of a block: either
    // the first line, or directly after a blank line.
    var starts = [];
    for (var i = 0; i < lines.length; i++) {
      var m = HEADER_RE.exec(lines[i]);
      if (m && m[1].toLowerCase() === "from") {
        if (i === 0 || lines[i - 1].trim() === "") starts.push(i);
      }
    }
    if (!starts.length) return [];

    starts.push(lines.length);
    var messages = [];
    for (var s = 0; s < starts.length - 1; s++) {
      var msg = parseBlock(lines.slice(starts[s], starts[s + 1]));
      if (msg) messages.push(msg);
    }
    return messages;
  }

  function parseBlock(block) {
    var headers = {};
    var bodyStart = block.length;
    var lastKey = null;
    for (var i = 0; i < block.length; i++) {
      var line = block[i];
      if (line.trim() === "") { bodyStart = i + 1; break; }
      var m = HEADER_RE.exec(line);
      if (m) {
        // Later duplicate headers win; fine for our well-formed exports.
        lastKey = m[1].toLowerCase();
        headers[lastKey] = m[2].trim();
      } else if (lastKey !== null && (line.charAt(0) === " " || line.charAt(0) === "\t")) {
        // Folded continuation of the previous header value (RFC 5322).
        headers[lastKey] = (headers[lastKey] + " " + line.trim()).trim();
      } else {
        // A non-header, non-continuation line ends the header area even with no
        // blank separator (malformed export). The rest is the body.
        bodyStart = i;
        break;
      }
    }

    var body = block.slice(bodyStart).join("\n").trim();

    var hasHeaders = false;
    for (var k in headers) { if (Object.prototype.hasOwnProperty.call(headers, k)) { hasHeaders = true; break; } }
    if (!hasHeaders && !body) return null;

    return {
      sender: headers["from"] || "",
      timestamp: headers["sent"] || headers["date"] || "",
      recipient: headers["to"] || "",
      subject: headers["subject"] || "",
      attachments: splitAttachments(headers["attachments"] || ""),
      body: body
    };
  }

  function splitAttachments(raw) {
    if (!raw.trim()) return [];
    return raw.split(/[;,]/).map(function (p) { return p.trim(); }).filter(Boolean);
  }

  // =======================================================================
  // normalize.py — strip quoted replies / forwards / signatures
  // =======================================================================
  var ATTRIB_START_RE = /^On\b/i;            // "On <date>, <person> wrote:"
  var WROTE_RE = /\bwrote:\s*$/i;
  var SEPARATOR_RE = /^\s*-{2,}\s*(original message|forwarded message)\s*-{2,}\s*$/i;
  var SIG_RE = /^--[ \t]?$/;                 // RFC 3676 signature delimiter

  function attributionIndex(lines) {
    for (var i = 0; i < lines.length; i++) {
      if (ATTRIB_START_RE.test(lines[i].trim())) {
        // The attribution can wrap across up to three physical lines.
        var window = lines.slice(i, i + 3).map(function (l) { return l.trim(); }).join(" ");
        if (WROTE_RE.test(window) || window.toLowerCase().indexOf("wrote:") !== -1) return i;
      }
    }
    return -1;
  }

  function stripQuoted(body) {
    var lines = splitlines(body);
    var cut = lines.length;
    for (var i = 0; i < lines.length; i++) {
      if (SEPARATOR_RE.test(lines[i])) { cut = i; break; }
    }
    var attrib = attributionIndex(lines);
    if (attrib !== -1) cut = Math.min(cut, attrib);

    var kept = lines.slice(0, cut).filter(function (l) {
      // Drop any standalone quoted ">" line (lstrip then check first char).
      return l.replace(/^\s+/, "").charAt(0) !== ">";
    });
    return kept.join("\n").trim();
  }

  function stripSignature(body) {
    var lines = splitlines(body);
    for (var i = 0; i < lines.length; i++) {
      if (SIG_RE.test(lines[i])) return lines.slice(0, i).join("\n").trim();
    }
    return body.trim();
  }

  function cleanForFingerprint(body) {
    return stripSignature(stripQuoted(body));
  }

  // =======================================================================
  // dedup.py — content keys + subset analysis
  // =======================================================================
  var ADDR_RE = /<([^>]+)>/;

  function normalizeSender(sender) {
    var m = ADDR_RE.exec(sender || "");
    if (m) return m[1].trim().toLowerCase();
    return (sender || "").trim().toLowerCase();
  }

  function fingerprintBody(body) {
    // Strip quotes/signature, then collapse whitespace and lowercase. Timestamps
    // never enter here, so timezone-shifted duplicates fingerprint identically.
    return cleanForFingerprint(body || "").split(/\s+/).filter(Boolean).join(" ").toLowerCase();
  }

  // Keys are stringified tuples so they behave as set members and stay
  // human-inspectable (and reversible) — exactly the Python ("msg"/"att", ...).
  function messageKey(msg) {
    return JSON.stringify(["msg", normalizeSender(msg.sender), fingerprintBody(msg.body)]);
  }

  function attachmentKey(name) {
    return JSON.stringify(["att", "", String(name).trim().toLowerCase()]);
  }

  function contentKeys(messages) {
    var keys = new Set();
    messages.forEach(function (msg) {
      keys.add(messageKey(msg));
      (msg.attachments || []).forEach(function (a) { keys.add(attachmentKey(a)); });
    });
    return keys;
  }

  function isSubset(a, b) {
    if (a.size > b.size) return false;
    return Array.prototype.every.call(Array.from(a), function (v) { return b.has(v); });
  }

  // file_keys: [{name, keys:Set}] -> [{name, redundant, supersededBy:[name]}]
  function analyze(fileKeys) {
    var items = fileKeys.slice().sort(function (x, y) {
      return x.name < y.name ? -1 : x.name > y.name ? 1 : 0;
    });
    return items.map(function (it) {
      var supersededBy = [];
      items.forEach(function (other) {
        if (other.name === it.name) return;
        var sub = isSubset(it.keys, other.keys);
        if (sub && it.keys.size < other.keys.size) {
          supersededBy.push(other.name);                       // strict subset
        } else if (it.keys.size === other.keys.size && sub && other.name < it.name) {
          supersededBy.push(other.name);                       // identical: keep one
        }
      });
      return { name: it.name, redundant: supersededBy.length > 0, supersededBy: supersededBy };
    });
  }

  // =======================================================================
  // High-level: files -> the state the UI renders (mirrors web.Session.state)
  // =======================================================================
  function computeState(inputFiles) {
    // inputFiles: [{name, content}]
    var parsed = inputFiles.map(function (f) {
      return { name: f.name, messages: parseThread(f.content || "") };
    });

    var fileKeys = parsed.map(function (p) {
      return { name: p.name, keys: contentKeys(p.messages) };
    });
    var reports = analyze(fileKeys);

    var keepSet = new Set();
    reports.forEach(function (r) { if (!r.redundant) keepSet.add(r.name); });

    // Index parsed messages by name for the viewer/compare, plus per-file info.
    var byName = {};
    var infoByName = {};
    parsed.forEach(function (p) {
      var atts = {};
      var viewMsgs = p.messages.map(function (m) {
        (m.attachments || []).forEach(function (a) { if (a.trim()) atts[a.trim()] = true; });
        return {
          from: m.sender, to: m.recipient, date: m.timestamp,
          subject: m.subject, body: m.body,
          attachments: (m.attachments || []).map(function (a) { return a.trim(); }).filter(Boolean),
          key: messageKey(m)
        };
      });
      byName[p.name] = viewMsgs;
      infoByName[p.name] = { name: p.name, messages: p.messages.length, attachments: Object.keys(atts).sort() };
    });

    // Summary counts mirror bridge.collect_unique_messages: dedup by message key.
    var total = 0;
    var uniqueMsg = new Set();
    parsed.forEach(function (p) {
      p.messages.forEach(function (m) { total += 1; uniqueMsg.add(messageKey(m)); });
    });

    var files = reports.map(function (r) {
      var info = infoByName[r.name] || { name: r.name, messages: 0, attachments: [] };
      var coveredBy = r.supersededBy.filter(function (n) { return keepSet.has(n); });
      if (!coveredBy.length) coveredBy = r.supersededBy.slice();
      return {
        name: r.name, messages: info.messages, attachments: info.attachments,
        redundant: r.redundant, coveredBy: coveredBy
      };
    });

    return {
      files: files,
      summary: {
        files: reports.length,
        kept: reports.filter(function (r) { return !r.redundant; }).length,
        redundant: reports.filter(function (r) { return r.redundant; }).length,
        uniqueMessages: uniqueMsg.size,
        duplicates: Math.max(0, total - uniqueMsg.size)
      },
      byName: byName
    };
  }

  var api = {
    splitlines: splitlines,
    parseThread: parseThread,
    cleanForFingerprint: cleanForFingerprint,
    normalizeSender: normalizeSender,
    fingerprintBody: fingerprintBody,
    messageKey: messageKey,
    attachmentKey: attachmentKey,
    contentKeys: contentKeys,
    analyze: analyze,
    computeState: computeState
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.ArcDedup = api;
  }
})(typeof self !== "undefined" ? self : this);
