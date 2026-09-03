"""Builds the static results dashboard (SPEC.md §6).

One self-contained HTML file: run data is embedded as JSON, so the site works
from a file:// URL, from GitHub Pages, and with no network access. Views:
leaderboard (governance x contribution), one system over time, comparison,
and per-scenario detail.
"""

from __future__ import annotations

import json
from pathlib import Path

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fleet Memory Bench — results</title>
<style>
 :root{--bg:#fbfbfa;--fg:#1b1b19;--mut:#6b6b66;--line:#e3e3df;--ok:#2f7d4f;--bad:#b4402f;--acc:#2b5c8a}
 @media(prefers-color-scheme:dark){:root{--bg:#16171a;--fg:#e8e8e4;--mut:#9a9a94;--line:#2c2e33;--ok:#6fbf8b;--bad:#e08472;--acc:#7fb0dd}}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
 header{padding:28px 32px 12px;border-bottom:1px solid var(--line)}
 h1{margin:0 0 4px;font-size:20px;letter-spacing:-.01em}
 .sub{color:var(--mut);font-size:13px;max-width:60ch}
 nav{display:flex;gap:4px;padding:12px 32px 0;border-bottom:1px solid var(--line)}
 nav button{background:none;border:0;border-bottom:2px solid transparent;padding:8px 12px;font:inherit;color:var(--mut);cursor:pointer}
 nav button.on{color:var(--fg);border-bottom-color:var(--acc)}
 main{padding:24px 32px 64px;max-width:1100px}
 section{display:none}section.on{display:block}
 table{border-collapse:collapse;width:100%;margin:12px 0 24px;font-variant-numeric:tabular-nums}
 th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}
 th{font-weight:600;color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
 td.num,th.num{text-align:right}
 .ok{color:var(--ok)}.bad{color:var(--bad)}
 .pill{display:inline-block;padding:1px 7px;border:1px solid var(--line);border-radius:99px;font-size:11px;color:var(--mut)}
 .plot{position:relative;height:420px;border:1px solid var(--line);border-radius:6px;margin:16px 0;background:
   linear-gradient(to right,transparent 0,transparent calc(100% - 1px),var(--line) 100%) 0 0/10% 100%,
   linear-gradient(to bottom,transparent 0,transparent calc(100% - 1px),var(--line) 100%) 0 0/100% 10%}
 .dot{position:absolute;width:11px;height:11px;border-radius:99px;background:var(--acc);transform:translate(-50%,50%);cursor:pointer}
 .dot span{position:absolute;left:14px;top:-6px;white-space:nowrap;font-size:12px;color:var(--fg)}
 .axis{position:absolute;color:var(--mut);font-size:11px}
 .scenario{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
 details{margin:4px 0}summary{cursor:pointer}
 .empty{color:var(--mut);padding:32px 0}
 select{font:inherit;padding:4px 6px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:4px}
</style></head><body>
<header>
 <h1>Fleet Memory Bench</h1>
 <div class="sub">Governance and contribution are reported as a pair and never combined.
 A memory that refuses everything scores 1.0 and 0.0; one that accepts everything scores the reverse.</div>
</header>
<nav>
 <button data-view="board" class="on">Leaderboard</button>
 <button data-view="system">System</button>
 <button data-view="compare">Compare</button>
 <button data-view="scenarios">Scenarios</button>
</nav>
<main>
 <section id="board" class="on"></section>
 <section id="system"></section>
 <section id="compare"></section>
 <section id="scenarios"></section>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const RUNS = JSON.parse(document.getElementById('data').textContent);
const GOV = ["C","A","T","E","S","G","F"];
const FAMS = GOV.concat(["R"]);
const fmt = n => (n===null||n===undefined) ? "—" : n.toFixed(3);
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

function latestBySystem(){
  // A partial run has no headline; it never appears on the leaderboard,
  // where a missing number would read as a score of zero.
  const by = {};
  for (const r of RUNS){
    if (r.headline.governance === null || r.headline.contribution === null) continue;
    const id = r.system.id;
    if (!by[id] || r.timestamp > by[id].timestamp) by[id] = r;
  }
  return Object.values(by).sort((a,b)=> b.headline.governance - a.headline.governance);
}

function board(){
  const rows = latestBySystem();
  if (!rows.length) return `<p class="empty">No runs yet. Run <code>fmb run --system null</code>, then <code>fmb ui</code>.</p>`;
  const dots = rows.map(r=>{
    const x = r.headline.contribution*100, y = r.headline.governance*100;
    return `<div class="dot" style="left:${x}%;bottom:${y}%" title="${esc(r.system.name)}"><span>${esc(r.system.id)}</span></div>`;
  }).join("");
  const table = rows.map(r=>`<tr>
     <td>${esc(r.system.name)} <span class="pill">${esc(r.system.version)}</span>${r._published?"":' <span class="pill">not submitted</span>'}</td>
     <td class="num">${fmt(r.headline.governance)}</td>
     <td class="num">${fmt(r.headline.contribution)}</td>
     ${FAMS.map(f=>`<td class="num ${r.families[f]&&r.families[f].rate===1?'ok':'bad'}">${r.families[f]?fmt(r.families[f].rate):"—"}</td>`).join("")}
     <td class="num">${r.policy?fmt(r.policy.rate):"—"}</td>
   </tr>`).join("");
  return `<h2>Governance × contribution</h2>
    <div class="plot">${dots}
      <div class="axis" style="left:8px;top:6px">governance 1.0</div>
      <div class="axis" style="left:8px;bottom:6px">0.0</div>
      <div class="axis" style="right:8px;bottom:6px">contribution 1.0</div>
    </div>
    <table><thead><tr><th>System</th><th class="num">Gov</th><th class="num">Contrib</th>
      ${FAMS.map(f=>`<th class="num">${f}</th>`).join("")}<th class="num">P</th></tr></thead>
      <tbody>${table}</tbody></table>
    <p class="sub">P is policy conformance: a system is graded against the choices it declared, and P is not part of either headline number.</p>`;
}

function systemView(){
  const ids = [...new Set(RUNS.map(r=>r.system.id))].sort();
  if (!ids.length) return `<p class="empty">No runs yet.</p>`;
  const chosen = window._sysId && ids.includes(window._sysId) ? window._sysId : ids[0];
  const runs = RUNS.filter(r=>r.system.id===chosen).sort((a,b)=>a.timestamp.localeCompare(b.timestamp));
  const partial = runs.filter(r=>r.headline.governance===null).length;
  const rows = runs.map(r=>`<tr>
      <td>${esc(r.system.version)}</td><td>${esc(r.timestamp)}</td>
      <td class="num">${fmt(r.headline.governance)}${r.headline.governance===null?' <span class="pill">partial</span>':''}</td><td class="num">${fmt(r.headline.contribution)}</td>
      ${FAMS.map(f=>`<td class="num">${r.families[f]?fmt(r.families[f].rate):"—"}</td>`).join("")}
    </tr>`).join("");
  const d = runs[runs.length-1].declarations || {};
  return `<h2>One system over time</h2>
    <p><select id="syspick">${ids.map(i=>`<option${i===chosen?" selected":""}>${esc(i)}</option>`).join("")}</select></p>
    <table><thead><tr><th>Version</th><th>When</th><th class="num">Gov</th><th class="num">Contrib</th>
      ${FAMS.map(f=>`<th class="num">${f}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>
    ${partial?`<p class="sub">${partial} partial run(s) shown: a run of a subset of families reports no headline, because a family that was never run has no rate.</p>`:""}
    <h3>Declared policy</h3>
    <table><tbody>${Object.entries(d).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join("")}</tbody></table>`;
}

function compare(){
  const rows = latestBySystem();
  if (rows.length < 2) return `<p class="empty">Two or more systems are needed to compare. ${rows.length} published.</p>`;
  return `<h2>Side by side</h2><table><thead><tr><th>Family</th>${rows.map(r=>`<th class="num">${esc(r.system.id)}</th>`).join("")}</tr></thead>
    <tbody>${FAMS.map(f=>`<tr><td>${f}</td>${rows.map(r=>`<td class="num">${r.families[f]?fmt(r.families[f].rate):"—"}</td>`).join("")}</tr>`).join("")}
    <tr><td><b>governance</b></td>${rows.map(r=>`<td class="num">${fmt(r.headline.governance)}</td>`).join("")}</tr>
    <tr><td><b>contribution</b></td>${rows.map(r=>`<td class="num">${fmt(r.headline.contribution)}</td>`).join("")}</tr>
    </tbody></table>`;
}

function scenarios(){
  const rows = latestBySystem();
  if (!rows.length) return `<p class="empty">No runs yet.</p>`;
  const ids = [...new Set(rows.flatMap(r=>r.scenarios.map(s=>s.measure||s.id.split("-")[0])))].sort();
  return `<h2>Every measure, and who fails it</h2>
    <table><thead><tr><th>Measure</th>${rows.map(r=>`<th class="num">${esc(r.system.id)}</th>`).join("")}</tr></thead>
    <tbody>${ids.map(m=>{
      const cells = rows.map(r=>{
        const ss = r.scenarios.filter(s=>(s.measure||s.id.split("-")[0])===m);
        if (!ss.length) return `<td class="num">—</td>`;
        const p = ss.filter(s=>s.passed).length;
        const cls = p===ss.length ? "ok" : "bad";
        return `<td class="num ${cls}">${p}/${ss.length}</td>`;
      }).join("");
      return `<tr><td class="scenario">${esc(m)}</td>${cells}</tr>`;
    }).join("")}</tbody></table>
    <p class="sub">A measure runs once per variant; the cell shows variants passed.</p>`;
}

const VIEWS = {board, system: systemView, compare, scenarios};
function render(){
  for (const [id, fn] of Object.entries(VIEWS)) document.getElementById(id).innerHTML = fn();
  const pick = document.getElementById('syspick');
  if (pick) pick.onchange = e => { window._sysId = e.target.value; render(); document.querySelector('nav button[data-view=system]').click(); };
}
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');
  document.getElementById(b.dataset.view).classList.add('on');
});
render();
</script></body></html>
"""


def build_site(runs: list[dict], out_dir: Path) -> Path:
    """Write a single self-contained index.html carrying every run."""
    out_dir.mkdir(parents=True, exist_ok=True)
    slim = []
    for run in runs:
        slim.append({
            "run_id": run["run_id"],
            "timestamp": run["timestamp"],
            "system": run["system"],
            "declarations": run.get("declarations", {}),
            "headline": run["headline"],
            "families": run["families"],
            "policy": run.get("policy", {}),
            "scenarios": [
                {"id": s["id"], "measure": s.get("measure", s["id"].split("-")[0]),
                 "family": s["family"], "passed": s["passed"],
                 "unsupported": s.get("unsupported", False)}
                for s in run["scenarios"]
            ],
            "_published": run.get("_published", False),
        })
    page = _PAGE.replace("__DATA__", json.dumps(slim))
    path = out_dir / "index.html"
    path.write_text(page, encoding="utf-8")
    return path
