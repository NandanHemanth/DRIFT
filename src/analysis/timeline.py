"""Replay a DRIFT run as a scrubbable bitemporal memory graph.

Why this is possible without instrumenting anything
---------------------------------------------------
A bitemporal fact carries its own history: `t_ingested` (when the agent learned
it), `t_invalid_at` (when a contradiction closed its valid-time window) and
`t_pruned` (when a policy dropped it). A final snapshot is therefore not a final
state -- it is a complete event log, and the whole run can be reconstructed from
it by filtering on time. That is the practical payoff of the substrate the
thesis argues for, so a viewer built this way is itself an argument.

What you see
------------
Drag the session slider and each fact moves through its lifecycle:

    invisible   -> not yet ingested
    green       -> active and current
    red dashed  -> superseded: a later fact closed its valid-time window, but
                   the fact is still in memory (this is what P0 keeps showing
                   the answer model, and what P2 filters out at retrieval)
    faded grey  -> pruned by the policy

Side-by-side mode puts two policies on one shared slider, which is the clearest
way to see the thesis's central mechanism: at the same session, P2 closes the
old fact's window while P3 never admitted the correction at all.

Node positions are solved once over the *final* graph and then held fixed, so
scrubbing does not reshuffle the layout -- you are watching the same map fill
in, not a new drawing each frame.

Legacy snapshots: runs made before `t_pruned` existed record *that* a fact was
pruned but not when. Those are shown as pruned only at the final session and
labelled accordingly, rather than being silently misplaced in time.

Usage:
    python analysis/timeline.py results/mquake_t/P2__openrouter_z-ai_glm-5.2.json
    python analysis/timeline.py results/mquake_t/P2__*.json results/mquake_t/P3__*.json
    python analysis/timeline.py results/mquake_t --policies P2,P3 -o docs/replay.html
"""
from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path


# --------------------------------------------------------------------------- #
# timeline construction
# --------------------------------------------------------------------------- #

def _session_times(cells: list[dict]) -> list[float]:
    """The union of ingestion times across every cell being shown.

    Taking the union rather than one cell's own times matters in comparison
    mode: two policies must share a slider, and a policy that rejects writes
    (P3) has strictly fewer distinct ingestion timestamps than one that does
    not. Indexing each panel on its own times would silently desynchronise them.
    """
    times = set()
    for c in cells:
        for f in c.get("graph_snapshot") or []:
            times.add(float(f["t_ingested"]))
    return sorted(times)


def _index_of(t: float | None, times: list[float]) -> int | None:
    """First session index at or after `t`. None passes through."""
    if t is None:
        return None
    for i, s in enumerate(times):
        if s >= t - 1e-6:
            return i
    return len(times) - 1


def build_panel(cell: dict, times: list[float], name: str) -> dict:
    """One policy's facts and entities, with lifecycle events as session indices."""
    facts = cell.get("graph_snapshot") or []
    summary = cell.get("summary", {})

    nodes: dict[str, dict] = {}
    edges = []
    for f in facts:
        s = (f["subject"] or "?").strip().lower()
        o = (f["object"] or "?").strip().lower()
        for ent, raw in ((s, f["subject"]), (o, f["object"])):
            if ent not in nodes:
                nodes[ent] = {"id": ent, "label": (raw or "?").strip(), "deg": 0}
            nodes[ent]["deg"] += 1

        pruned_at = _index_of(f.get("t_pruned"), times)
        # Legacy snapshot: inactive but no prune timestamp. Place it at the end
        # and flag it, rather than guessing a session it might not belong to.
        legacy = pruned_at is None and not f.get("active", True)
        edges.append({
            "s": s, "o": o,
            "p": f["predicate"],
            "txt": f["text"],
            "in": _index_of(float(f["t_ingested"]), times),
            "inv": _index_of(f.get("t_invalid_at"), times),
            "pr": (len(times) - 1) if legacy else pruned_at,
            "lg": legacy,
        })

    return {
        "name": name,
        "policy": summary.get("policy", name),
        "model": summary.get("model", ""),
        "accuracy": summary.get("accuracy"),
        "staleness": summary.get("staleness_rate"),
        "nodes": sorted(nodes.values(), key=lambda n: -n["deg"]),
        "edges": edges,
        "curves": cell.get("memory_curves") or [],
    }


def build(cells: list[dict], names: list[str]) -> dict:
    times = _session_times(cells)
    if not times:
        raise SystemExit(
            "no graph_snapshot in these results -- rerun with \"save_graph\": true")
    panels = [build_panel(c, times, n) for c, n in zip(cells, names)]

    # Sessions at which *any* panel records a supersession, so the viewer can
    # offer "jump to the next interesting moment" instead of making someone
    # drag a 38-step slider hunting for one.
    events = sorted({e["inv"] for p in panels for e in p["edges"]
                     if e["inv"] is not None})
    return {
        "times": [datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
                  for t in times],
        "panels": panels,
        "events": events,
    }


# --------------------------------------------------------------------------- #
# viewer
# --------------------------------------------------------------------------- #

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>DRIFT - bitemporal memory replay</title><style>
*{box-sizing:border-box}
body{margin:0;background:#0f1117;color:#e6e9f0;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{padding:12px 18px;border-bottom:1px solid #232838;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
h1{font-size:15px;margin:0;font-weight:600}
#ctl{display:flex;gap:10px;align-items:center;flex:1;min-width:340px}
input[type=range]{flex:1;accent-color:#2a9d8f}
button{background:#1d2231;color:#e6e9f0;border:1px solid #2f374b;border-radius:6px;padding:5px 11px;font:inherit;cursor:pointer}
button:hover{background:#262d40}
#when{font-variant-numeric:tabular-nums;min-width:190px;color:#9aa4bd}
#wrap{display:flex;height:calc(100vh - 58px)}
.panel{flex:1;position:relative;border-right:1px solid #232838;overflow:hidden}
.panel:last-child{border-right:none}
.ttl{position:absolute;top:10px;left:12px;z-index:2;background:#181c26cc;padding:7px 11px;border-radius:7px;backdrop-filter:blur(3px)}
.ttl b{color:#fff}.ttl span{color:#9aa4bd}
svg{width:100%;height:100%;display:block}
text{fill:#8f98b2;font-size:9px;pointer-events:none}
.e{stroke-width:1.4}
.act{stroke:#2a9d8f;opacity:.75}
.inv{stroke:#c94f5e;stroke-dasharray:4 3;stroke-width:2;opacity:.95}
.pru{stroke:#39405a;opacity:.28;stroke-dasharray:1 4}
#log{width:340px;background:#12151f;border-left:1px solid #232838;overflow-y:auto;padding:12px 14px}
#log h2{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6e7794;margin:0 0 9px}
.ev{padding:6px 8px;margin-bottom:5px;border-radius:5px;background:#181c26;border-left:3px solid #39405a;font-size:12px}
.ev.a{border-left-color:#2a9d8f}.ev.i{border-left-color:#c94f5e}.ev.p{border-left-color:#5a6382}
.ev .k{color:#6e7794;font-size:10px;text-transform:uppercase;letter-spacing:.06em}
.stat{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:12px;padding-bottom:11px;border-bottom:1px solid #232838}
.stat div{font-size:11px;color:#6e7794}.stat b{display:block;font-size:16px;color:#e6e9f0;font-variant-numeric:tabular-nums}
.lgd{display:flex;gap:14px;font-size:11px;color:#9aa4bd;align-items:center}
.sw{display:inline-block;width:13px;height:3px;margin-right:5px;vertical-align:middle}
</style></head><body>
<header>
  <h1>DRIFT · bitemporal memory replay</h1>
  <div id="ctl">
    <button id="play">▶ Play</button>
    <button id="next">Next supersession →</button>
    <input type="range" id="sl" min="0" value="0">
    <span id="when"></span>
  </div>
  <div class="lgd">
    <span><i class="sw" style="background:#2a9d8f"></i>active</span>
    <span><i class="sw" style="background:#c94f5e"></i>superseded</span>
    <span><i class="sw" style="background:#39405a"></i>pruned</span>
  </div>
</header>
<div id="wrap"><div id="panels" style="display:flex;flex:1"></div><div id="log"></div></div>
<script>
const D = __DATA__;
const P = D.panels, T = D.times;
const sl = document.getElementById('sl'); sl.max = T.length - 1;

// One layout per panel, solved once over the FINAL graph and then frozen.
// Recomputing per frame would reshuffle the map on every slider step and make
// the replay unreadable -- the point is to watch one map fill in.
P.forEach(p => {
  const W = 900, H = 700, idx = {};
  p.nodes.forEach((n, i) => { idx[n.id] = i;
    n.x = W/2 + Math.cos(i*2.4)*(70+7*i%330); n.y = H/2 + Math.sin(i*2.4)*(55+5*i%260);
    n.vx = 0; n.vy = 0; });
  p.idx = idx; p.W = W; p.H = H;
  for (let it = 0; it < 220; it++) {
    p.nodes.forEach(a => {
      p.nodes.forEach(b => { if (a === b) return;
        let dx = a.x-b.x, dy = a.y-b.y, d2 = dx*dx+dy*dy+.01, f = 900/d2;
        a.vx += dx*f/Math.sqrt(d2); a.vy += dy*f/Math.sqrt(d2); });
      a.vx += (W/2-a.x)*.003; a.vy += (H/2-a.y)*.003; });
    p.edges.forEach(e => {
      const a = p.nodes[idx[e.s]], b = p.nodes[idx[e.o]]; if (!a||!b) return;
      const dx = b.x-a.x, dy = b.y-a.y, d = Math.sqrt(dx*dx+dy*dy)+.01, f = (d-95)*.012;
      a.vx += dx/d*f; a.vy += dy/d*f; b.vx -= dx/d*f; b.vy -= dy/d*f; });
    p.nodes.forEach(n => { n.x += n.vx *= .55; n.y += n.vy *= .55;
      n.x = Math.max(26, Math.min(W-26, n.x)); n.y = Math.max(22, Math.min(H-22, n.y)); });
  }
});

document.getElementById('panels').innerHTML = P.map((p, i) => `
  <div class="panel"><div class="ttl"><b>${p.policy}</b>
    <span>${p.model ? '· ' + p.model.split('/').pop() : ''}</span><br>
    <span id="pstat${i}"></span></div>
  <svg id="svg${i}" viewBox="0 0 ${p.W} ${p.H}" preserveAspectRatio="xMidYMid meet"></svg></div>`).join('');

// A fact's class at session t is decided purely by comparing t against the
// timestamps the fact itself carries -- no simulation, no replay of the run.
function state(e, t) {
  if (e.in === null || e.in > t) return null;         // not yet learned
  if (e.pr !== null && e.pr <= t) return 'pru';       // policy dropped it
  if (e.inv !== null && e.inv <= t) return 'inv';     // valid window closed
  return 'act';
}

function draw(t) {
  P.forEach((p, i) => {
    const live = {}, parts = [];
    p.edges.forEach(e => {
      const st = state(e, t); if (!st) return;
      const a = p.nodes[p.idx[e.s]], b = p.nodes[p.idx[e.o]]; if (!a||!b) return;
      if (st !== 'pru') { live[e.s] = 1; live[e.o] = 1; }
      parts.push(`<line class="e ${st}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"><title>${esc(e.txt)}</title></line>`);
    });
    const ns = p.nodes.filter(n => live[n.id]).map(n =>
      `<g><circle cx="${n.x}" cy="${n.y}" r="${3.5+Math.min(9, n.deg)}" fill="#2a9d8f" opacity=".82"><title>${esc(n.label)}</title></circle>` +
      (n.deg > 2 ? `<text x="${n.x+8}" y="${n.y+3}">${esc(n.label).slice(0,26)}</text>` : '') + `</g>`).join('');
    document.getElementById('svg'+i).innerHTML = parts.join('') + ns;

    const c = p.curves[Math.min(t, p.curves.length-1)] || {};
    document.getElementById('pstat'+i).textContent =
      `${c.active_facts ?? '–'} active · ${c.invalidated_active ?? '–'} superseded · ${c.pruned ?? '–'} pruned` +
      (c.write_rejections ? ` · ${c.write_rejections} writes rejected` : '');
  });
  renderLog(t);
  document.getElementById('when').textContent = `session ${t+1}/${T.length} · ${T[t]}`;
}

function renderLog(t) {
  const c0 = P[0].curves[Math.min(t, P[0].curves.length-1)] || {};
  let h = `<div class="stat">
    <div>ACTIVE<b>${c0.active_facts ?? '–'}</b></div>
    <div>SUPERSEDED<b>${c0.invalidated_active ?? '–'}</b></div>
    <div>PRUNED<b>${c0.pruned ?? '–'}</b></div>
    <div>REJECTED<b>${c0.write_rejections ?? 0}</b></div></div>
    <h2>Session ${t+1} - ${T[t]}</h2>`;
  let n = 0;
  P.forEach(p => {
    const pre = P.length > 1 ? `<span class="k">${p.policy}</span> ` : '';
    p.edges.forEach(e => {
      if (e.inv === t) { h += `<div class="ev i">${pre}<span class="k">superseded</span><br>${esc(e.txt)}</div>`; n++; }
    });
    p.edges.forEach(e => {
      if (e.pr === t && !e.lg) { h += `<div class="ev p">${pre}<span class="k">pruned</span><br>${esc(e.txt)}</div>`; n++; }
    });
    p.edges.filter(e => e.in === t).slice(0, 8).forEach(e => {
      h += `<div class="ev a">${pre}<span class="k">learned</span><br>${esc(e.txt)}</div>`; n++;
    });
  });
  if (!n) h += `<div class="ev">no memory events this session</div>`;
  document.getElementById('log').innerHTML = h;
}

const esc = s => String(s).replace(/[<>&"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));

sl.oninput = () => draw(+sl.value);
document.getElementById('next').onclick = () => {
  const t = +sl.value, nx = D.events.find(e => e > t);
  sl.value = nx === undefined ? (D.events[0] ?? 0) : nx; draw(+sl.value);
};
let timer = null;
document.getElementById('play').onclick = e => {
  if (timer) { clearInterval(timer); timer = null; e.target.textContent = '▶ Play'; return; }
  e.target.textContent = '❚❚ Pause';
  timer = setInterval(() => {
    if (+sl.value >= sl.max) { clearInterval(timer); timer = null; e.target.textContent = '▶ Play'; return; }
    sl.value = +sl.value + 1; draw(+sl.value);
  }, 650);
};
draw(0);
</script></body></html>"""


# --------------------------------------------------------------------------- #

def _resolve(args_paths: list[str], policies: str | None) -> list[Path]:
    """Accept explicit cell JSONs, shell globs, or a results dir + --policies."""
    out: list[Path] = []
    for raw in args_paths:
        p = Path(raw)
        if p.is_dir():
            wanted = [s.strip() for s in (policies or "").split(",") if s.strip()]
            cells = sorted(x for x in p.glob("*.json")
                           if x.name != "summary_table.json"
                           and not x.name.endswith(".graph.json"))
            if wanted:
                picked = []
                for w in wanted:
                    match = [c for c in cells if c.name.split("__")[0] == w]
                    if not match:
                        raise SystemExit(f"no cell for policy {w!r} in {p}")
                    picked.append(match[0])
                out += picked
            else:
                out += cells[:1]
        else:
            out += [Path(g) for g in sorted(glob.glob(raw))] or [p]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Scrubbable replay of a DRIFT bitemporal memory graph")
    ap.add_argument("paths", nargs="+",
                    help="result cell JSON(s), a glob, or a results dir")
    ap.add_argument("--policies", default=None,
                    help="with a results dir: comma-separated policies to compare, "
                         "e.g. --policies P2,P3")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    paths = _resolve(args.paths, args.policies)
    if not paths:
        raise SystemExit("no result cells matched")
    if len(paths) > 3:
        raise SystemExit(f"{len(paths)} cells given; the viewer shows at most 3 "
                         "side by side. Narrow it with --policies.")

    cells, names = [], []
    for p in paths:
        data = json.loads(p.read_text())
        if not data.get("graph_snapshot"):
            raise SystemExit(f"{p} has no graph_snapshot -- rerun that config with "
                             "\"save_graph\": true")
        cells.append(data)
        names.append(p.name.split("__")[0])

    payload = build(cells, names)
    default = (paths[0].parent /
               f"replay_{'_vs_'.join(names)}.html")
    out = Path(args.out) if args.out else default
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(HTML.replace("__DATA__", json.dumps(payload)))

    legacy = sum(1 for p in payload["panels"] for e in p["edges"] if e["lg"])
    print(f"replay -> {out}")
    print(f"  {len(payload['times'])} sessions · "
          f"{' vs '.join(p['policy'] for p in payload['panels'])} · "
          f"{len(payload['events'])} sessions containing a supersession")
    if legacy:
        print(f"  note: {legacy} facts were pruned by a run predating t_pruned; "
              "they appear only at the final session. Rerun to place them in time.")


if __name__ == "__main__":
    main()
