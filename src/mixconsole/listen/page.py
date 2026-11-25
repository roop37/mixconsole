"""The single-file listening page. No network access: no external scripts, fonts or analytics."""

import json

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MixConsole listening test</title>
<style>
:root { --bg:#fafaf7; --fg:#1b1b1b; --muted:#666; --card:#fff; --line:#d9d9d2; --accent:#1f5fbf; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161616; --fg:#eee; --muted:#9a9a9a; --card:#202020; --line:#383838; --accent:#6aa3ff; }
}
body { margin:0; padding:16px; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui,sans-serif; }
main { max-width:760px; margin:0 auto; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:16px; margin:16px 0; }
button { font:inherit; padding:8px 14px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--fg); cursor:pointer; }
button.primary { background:var(--accent); color:#fff; border-color:var(--accent); }
button[disabled] { opacity:.5; cursor:default; }
nav button[aria-pressed="true"] { border-color:var(--accent); font-weight:600; }
audio { width:100%; margin:6px 0; }
.row { display:grid; grid-template-columns:5em 1fr; gap:8px; align-items:center; margin:8px 0; }
.muted { color:var(--muted); font-size:14px; }
input[type=range] { width:100%; }
input[type=text] { font:inherit; padding:6px 8px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--fg); }
</style>
</head>
<body>
<main>
<h1>MixConsole listening test</h1>
<p class="muted">Everything runs in this page. Nothing is uploaded; votes stay in this browser until you save them as a JSON file.
Use headphones and a comfortable volume. Judge how natural and musical each transition between the two songs sounds.</p>
<div class="card">
  <label>Your name or ID <input type="text" id="rater" autocomplete="off"></label>
  <nav style="margin-top:12px">
    <button id="tab-ab" aria-pressed="true">A/B comparison</button>
    <button id="tab-mushra" aria-pressed="false">Rating (MUSHRA-lite)</button>
  </nav>
</div>
<section id="view"></section>
<div class="card">
  <button id="save" class="primary">Save votes as JSON</button>
  <button id="clear">Clear my votes</button>
  <span class="muted" id="status"></span>
</div>
</main>
<script id="kit" type="application/json">__CONFIG__</script>
<script>
"use strict";
const KIT = JSON.parse(document.getElementById("kit").textContent);
const STORE = "mixconsole-listen-" + KIT.kit_id;
let state = { rater: "", ab: {}, mushra: {} };
try { state = Object.assign(state, JSON.parse(localStorage.getItem(STORE) || "{}")); } catch (e) {}
function persist() { try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {} }
function hash(text) { let h = 2166136261; for (const c of text) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { return function () { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function shuffled(list, seed) { const r = rng(seed), a = list.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
function player(token, label) {
  const row = document.createElement("div"); row.className = "row";
  const name = document.createElement("strong"); name.textContent = label;
  const audio = document.createElement("audio"); audio.controls = true; audio.preload = "none"; audio.src = KIT.audio[token];
  row.append(name, audio); return row;
}
function order(kind, items) { return shuffled(items, hash(kind + KIT.kit_id + (state.rater || ""))); }
let tab = "ab", index = { ab: 0, mushra: 0 };
function showAB() {
  const trials = order("ab", KIT.ab), view = document.getElementById("view"); view.textContent = "";
  if (!trials.length) { view.textContent = "No A/B trials in this kit."; return; }
  const i = Math.min(index.ab, trials.length - 1), t = trials[i], card = document.createElement("div"); card.className = "card";
  const head = document.createElement("p"); head.textContent = "Trial " + (i + 1) + " of " + trials.length + " - " + t.title; card.append(head);
  card.append(player(t.left, "A"), player(t.right, "B"));
  const q = document.createElement("p"); q.textContent = "Which transition sounds better?"; card.append(q);
  for (const [value, text] of [["left", "A is better"], ["tie", "No preference"], ["right", "B is better"]]) {
    const b = document.createElement("button"); b.textContent = text; b.dataset.choice = value;
    if ((state.ab[t.id] || {}).choice === value) b.className = "primary";
    b.onclick = function () { state.ab[t.id] = { trial: t.id, pair: t.pair, left: t.left, right: t.right, choice: value }; persist(); status(); showAB(); };
    card.append(b, " ");
  }
  const nav = document.createElement("p");
  const prev = document.createElement("button"); prev.textContent = "Previous"; prev.disabled = i === 0; prev.onclick = function () { index.ab = i - 1; showAB(); };
  const next = document.createElement("button"); next.textContent = "Next"; next.disabled = i === trials.length - 1; next.onclick = function () { index.ab = i + 1; showAB(); };
  nav.append(prev, " ", next); card.append(nav); view.append(card);
}
function showMushra() {
  const sets = order("mushra", KIT.mushra), view = document.getElementById("view"); view.textContent = "";
  if (!sets.length) { view.textContent = "No rating sets in this kit."; return; }
  const i = Math.min(index.mushra, sets.length - 1), s = sets[i], card = document.createElement("div"); card.className = "card";
  const head = document.createElement("p"); head.textContent = "Set " + (i + 1) + " of " + sets.length + " - " + s.title; card.append(head);
  card.append(player(s.reference, "Original"));
  const note = document.createElement("p"); note.className = "muted";
  note.textContent = "Rate every item 0-100 (100 = as natural as the original, 0 = unusable). One of them is the original itself.";
  card.append(note);
  const saved = (state.mushra[s.pair] || {}).scores || {};
  shuffled(s.items, hash("items" + s.pair + (state.rater || ""))).forEach(function (token, n) {
    const wrap = document.createElement("div"); wrap.append(player(token, "Item " + (n + 1)));
    const row = document.createElement("div"); row.className = "row";
    const out = document.createElement("span"); out.textContent = token in saved ? saved[token] : "-";
    const range = document.createElement("input"); range.type = "range"; range.min = 0; range.max = 100; range.value = token in saved ? saved[token] : 50;
    range.dataset.token = token;
    range.oninput = function () {
      const scores = (state.mushra[s.pair] || { pair: s.pair, scores: {} }).scores; scores[token] = Number(range.value);
      state.mushra[s.pair] = { pair: s.pair, scores: scores }; out.textContent = range.value; persist(); status();
    };
    row.append(out, range); wrap.append(row); card.append(wrap);
  });
  const nav = document.createElement("p");
  const prev = document.createElement("button"); prev.textContent = "Previous"; prev.disabled = i === 0; prev.onclick = function () { index.mushra = i - 1; showMushra(); };
  const next = document.createElement("button"); next.textContent = "Next"; next.disabled = i === sets.length - 1; next.onclick = function () { index.mushra = i + 1; showMushra(); };
  nav.append(prev, " ", next); card.append(nav); view.append(card);
}
function render() { (tab === "ab" ? showAB : showMushra)(); }
function status() {
  const done = Object.keys(state.ab).length, rated = Object.keys(state.mushra).length;
  document.getElementById("status").textContent = " A/B " + done + "/" + KIT.ab.length + ", ratings started " + rated + "/" + KIT.mushra.length;
}
function select(next) { tab = next; index = { ab: 0, mushra: 0 }; document.getElementById("tab-ab").setAttribute("aria-pressed", String(next === "ab")); document.getElementById("tab-mushra").setAttribute("aria-pressed", String(next === "mushra")); render(); }
document.getElementById("tab-ab").onclick = function () { select("ab"); };
document.getElementById("tab-mushra").onclick = function () { select("mushra"); };
const rater = document.getElementById("rater"); rater.value = state.rater;
rater.onchange = function () { state.rater = rater.value.trim(); persist(); render(); };
document.getElementById("save").onclick = function () {
  const votes = { version: "listen-votes/v1", kit_id: KIT.kit_id, rater: state.rater || "anonymous", saved: new Date().toISOString(), ab: Object.values(state.ab), mushra: Object.values(state.mushra) };
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([JSON.stringify(votes, null, 2)], { type: "application/json" }));
  link.download = "votes-" + (state.rater || "anonymous").replace(/[^A-Za-z0-9_-]+/g, "_") + "-" + KIT.kit_id + ".json";
  document.body.append(link); link.click(); link.remove();
};
document.getElementById("clear").onclick = function () { if (confirm("Delete all votes stored in this browser?")) { state = { rater: state.rater, ab: {}, mushra: {} }; persist(); status(); render(); } };
status(); render();
</script>
</body>
</html>
"""


def render_page(config: dict[str, object]) -> str:
    """Embed the kit config; ``</`` is escaped so the JSON can never close the script tag."""
    payload = json.dumps(config, separators=(",", ":")).replace("</", "<\\/")
    return _TEMPLATE.replace("__CONFIG__", payload)
