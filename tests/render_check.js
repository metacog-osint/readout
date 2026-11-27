// Runs site/app.js against site/data/snapshot.json with a minimal DOM stand-in, and prints what each table drew.
// No browser here: this checks that the page script runs on the built data and fills every section.
// Usage: node tests/render_check.js site
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const dir = process.argv[2] || "site";
const snap = JSON.parse(fs.readFileSync(path.join(dir, "data", "snapshot.json"), "utf8"));
const els = {};
function el(id) {
  if (!els[id]) { els[id] = { id, innerHTML: "", textContent: "", value: "", listeners: {}, addEventListener(t, f) { this.listeners[t] = f; }, scrollIntoView() {} }; }
  return els[id];
}
const ctx = {
  window: {}, location: { hash: "" }, console,
  document: { getElementById: el },
  fetch: () => Promise.resolve({ json: () => Promise.resolve(snap) }),
};
ctx.window.TicTime = undefined;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(dir, "app.js"), "utf8"), ctx);
setTimeout(() => {
  const out = {};
  for (const id of ["asof", "tiles", "saydo", "threats", "statements", "votes", "lanes", "f-count"]) {
    const h = els[id] ? (els[id].innerHTML || els[id].textContent) : "";
    out[id] = { chars: h.length, rows: (h.match(/<tr/g) || []).length, text: h.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").slice(0, 160) };
  }
  if (/Could not load/.test(out.asof.text)) { console.error("FAIL", out.asof.text); process.exit(1); }
  console.log(JSON.stringify(out, null, 1));
}, 50);
