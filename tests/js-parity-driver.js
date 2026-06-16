/*
 * js-parity-driver.js — run the browser dedup port over a folder and print its
 * verdict as JSON, so tests/test_js_parity.py can assert it matches `arc dedup`.
 *
 * Usage:  node tests/js-parity-driver.js <dir>
 * Output: {"keep":[...], "delete":[...], "files":[{name,redundant,coveredBy}],
 *          "summary":{...}}  (names sorted)
 *
 * Only .txt files are read — the JS port handles the plain-text export format
 * (the .eml/.mbox readers live in Python's stdlib email/mailbox modules).
 */
"use strict";
var fs = require("fs");
var path = require("path");
var ArcDedup = require(path.join(__dirname, "..", "docs", "arc-dedup.js"));

var dir = process.argv[2];
if (!dir) {
  process.stderr.write("usage: node js-parity-driver.js <dir>\n");
  process.exit(2);
}

var records = fs.readdirSync(dir)
  .filter(function (n) { return /\.txt$/i.test(n); })
  .sort()
  .map(function (n) {
    return { name: n, content: fs.readFileSync(path.join(dir, n), "utf8") };
  });

var state = ArcDedup.computeState(records);
var keep = state.files.filter(function (f) { return !f.redundant; }).map(function (f) { return f.name; }).sort();
var del = state.files.filter(function (f) { return f.redundant; }).map(function (f) { return f.name; }).sort();

process.stdout.write(JSON.stringify({
  keep: keep,
  delete: del,
  files: state.files.map(function (f) {
    return { name: f.name, redundant: f.redundant, coveredBy: f.coveredBy.slice().sort() };
  }),
  summary: state.summary
}));
