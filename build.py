"""Builds the installable app (index.html, icons) from ../living-plan.html.
Run: python build.py
"""
import os, re
from PIL import Image, ImageDraw

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "..", "living-plan.html"), encoding="utf-8").read()

# 1. Storage: swap the claude.ai store for the phone's own storage.
old_use = '(window.claude && typeof window.claude.use === "function") ? await window.claude.use("db") : null'
assert old_use in src
src = src.replace(old_use, "window.__lp.db")

# 2. Wording that only fits the hosted page.
swaps = {
    "<title>Living Plan 2027</title>": "",
    '<meta name="claude:viewport-fit-sides" content="cover">': "",
    "Loading your plan…": "Starting…",
    '\n      <button class="btn small" id="copyData" type="button" style="margin-top:6px">Copy all data</button>': "",
    "No cells yet. Add your first one to start the plan.": "No cells yet. Scroll down to Backup and paste your plan data, or add your first cell.",
    'sync("Up to date.")': 'sync("Saved on this phone.")',
    'sync("Saved.")': 'sync("Saved on this phone.")',
}
for a, b in swaps.items():
    assert a in src, a
    src = src.replace(a, b)

backup = """
  <section class="panel" aria-label="Backup">
    <h2>Backup</h2>
    <p class="note" style="margin:0">Your plan is stored on this device only. Copy it out now and then, and paste it in here to restore it or to bring it over from the Living Plan page.</p>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn" id="expBtn" type="button">Copy all data</button>
      <button class="btn" id="impBtn" type="button">Paste data in</button>
    </div>
    <div id="impBox" hidden style="display:grid;gap:8px">
      <textarea id="impText" placeholder="Paste the copied plan data here" aria-label="Plan data"></textarea>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn primary" id="impGo" type="button">Replace my plan with this</button>
        <button class="btn" id="impCancel" type="button">Cancel</button>
      </div>
    </div>
    <p class="note" id="bkMsg" style="margin:0"></p>
  </section>
</div>

<script>
"""
marker = "\n</div>\n\n<script>\n"
assert src.count(marker) == 1
src = src.replace(marker, backup)

store = """<script>
// The plan lives in this device's storage. This object mimics the small part of the hosted store the page uses.
window.__lp = (() => {
  const KEY = "living-plan-v1";
  let areas = {}, listener = null;
  try { areas = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (_) { areas = {}; }
  const persist = () => { try { localStorage.setItem(KEY, JSON.stringify(areas)); return Promise.resolve(); } catch (e) { return Promise.reject({ code: "quota_exceeded" }); } };
  const snap = () => ({ metadata: { fromCache: false, hasPendingWrites: false }, docs: Object.keys(areas).map(id => ({ id, data: () => areas[id] })) });
  const db = {
    doc: path => { const id = path.split("/")[1]; return { set: body => { areas[id] = body; return persist(); }, delete: () => { delete areas[id]; return persist(); } }; },
    collection: () => ({ onSnapshot: next => { listener = next; setTimeout(() => next(snap()), 0); return () => { listener = null; }; } }),
  };
  return {
    db,
    exportText: () => JSON.stringify({ app: "living-plan", v: 1, exported: new Date().toISOString(), areas: Object.keys(areas).map(id => ({ id, ...areas[id] })) }),
    importText: text => {
      const data = JSON.parse(text);
      if (!data || data.app !== "living-plan" || !Array.isArray(data.areas)) throw new Error("not plan data");
      const next = {};
      for (const a of data.areas) {
        if (!a || typeof a.id !== "string" || !/^[A-Za-z0-9_-]{1,60}$/.test(a.id)) continue;
        next[a.id] = { name: String(a.name || "Untitled").slice(0, 60), order: Number(a.order) || 0, hue: Number(a.hue) || 1, summary: String(a.summary || ""),
          items: (Array.isArray(a.items) ? a.items : []).filter(i => i && typeof i.text === "string").map(i => ({ id: String(i.id || Math.random().toString(36).slice(2)), kind: ["task", "note", "date", "link"].includes(i.kind) ? i.kind : "note", text: i.text, date: /^\\d{4}-\\d{2}-\\d{2}$/.test(i.date || "") ? i.date : "", done: !!i.done, created: String(i.created || "") })) };
      }
      areas = next;
      return persist().then(() => { if (listener) listener(snap()); return Object.keys(next).length; });
    },
  };
})();
</script>
"""

tail = """
<script>
(() => {
  const $ = s => document.querySelector(s), msg = t => { $("#bkMsg").textContent = t; };
  $("#expBtn").addEventListener("click", () => {
    const text = window.__lp.exportText();
    const fallback = () => { $("#impBox").hidden = false; $("#impText").value = text; $("#impText").select(); msg("Copying was blocked. The data is in the box: select all and copy it."); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(() => msg("Copied. Paste it somewhere safe, such as a note."), fallback); else fallback();
  });
  $("#impBtn").addEventListener("click", () => { $("#impBox").hidden = false; $("#impText").value = ""; $("#impText").focus(); msg(""); });
  $("#impCancel").addEventListener("click", () => { $("#impBox").hidden = true; msg(""); });
  $("#impGo").addEventListener("click", () => {
    try {
      window.__lp.importText($("#impText").value.trim()).then(n => { $("#impBox").hidden = true; $("#impText").value = ""; msg(n + " cells loaded."); window.scrollTo(0, 0); },
        () => msg("This device's storage is full, so the plan wasn't saved."));
    } catch (_) { msg("That isn't plan data. Copy it again with the Copy all data button and paste the whole thing."); }
  });
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
})();
</script>
"""

head = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Living Plan</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Living Plan">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="theme-color" content="#f1f0f6" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#14121d" media="(prefers-color-scheme: dark)">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" href="icon-192.png">
<style>html{-webkit-text-size-adjust:100%}body{margin:0;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}[hidden]{display:none!important}input,select,textarea,button{font-size:16px}</style>
</head>
<body>
"""
# the store must exist before the page script runs
first_script = src.index("<script>\n(() => {")
html = head + src[:first_script] + store + src[first_script:] + tail + "</body>\n</html>\n"
open(os.path.join(here, "index.html"), "w", encoding="utf-8").write(html)

# Icons: a stained cell on a pale slide.
def icon(size):
    s = size * 4
    im = Image.new("RGB", (s, s), (241, 240, 246))
    d = ImageDraw.Draw(im)
    def blob(cx, cy, rx, ry, fill, outline, w):
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline, width=w)
    blob(s * .44, s * .47, s * .30, s * .27, (214, 203, 240), (90, 63, 163), int(s * .028))
    blob(s * .70, s * .66, s * .15, s * .16, (244, 208, 224), (199, 65, 122), int(s * .024))
    blob(s * .69, s * .27, s * .09, s * .09, (203, 232, 236), (31, 127, 140), int(s * .020))
    blob(s * .41, s * .45, s * .10, s * .09, (90, 63, 163), (90, 63, 163), 1)
    return im.resize((size, size), Image.LANCZOS)
for n in (180, 192, 512):
    icon(n).save(os.path.join(here, "icon-%d.png" % n))
print("built", len(html), "bytes")
