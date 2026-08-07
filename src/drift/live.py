"""Opt-in live view: watch memory build while a run is in progress.

Turn on with `"live": true` in a config (or `--live` on the runner). After every
ingested session the runner drops a slim snapshot at `<results_dir>/live.json`
and, once, a `live.html` that polls it.

Three rules this module obeys, because a monitoring feature that can break a
six-hour campaign is worse than no monitoring feature:

  * **Never raise.** Every write is wrapped; a full disk or a locked file costs
    you the live view, not the run.
  * **Never block.** Writes go to a temp file and are then atomically renamed,
    so a page that polls mid-write reads the previous complete snapshot rather
    than a truncated one.
  * **Never carry embeddings.** A 768-dimension vector per fact would make the
    snapshot two orders of magnitude larger than the part anyone looks at, and
    it would be rewritten every session.

The page is deliberately a poller over a plain file rather than a server: it
works over `file://`, needs no port, no dependency and no cleanup, and the same
artifact keeps working after the run finishes as a static record of the final
state.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# Fields the viewer needs. Everything else -- embeddings above all -- is dropped.
_KEEP = ("subject", "predicate", "object", "text",
         "t_valid_start", "t_ingested", "t_invalid_at", "t_pruned", "active")


def slim(facts) -> list[dict]:
    out = []
    for f in facts:
        d = f.to_dict() if hasattr(f, "to_dict") else dict(f)
        out.append({k: d.get(k) for k in _KEEP})
    return out


def write(results_dir: str | Path, *, policy: str, model: str, conversation: str,
          session: int, n_sessions: int, graph, curves: list[dict]) -> None:
    """Atomically publish the current memory state. Silent on any failure."""
    try:
        d = Path(results_dir)
        d.mkdir(parents=True, exist_ok=True)
        payload = {
            "policy": policy, "model": model, "conversation": conversation,
            "session": session, "n_sessions": n_sessions,
            "stats": graph.stats(),
            "curves": curves[-200:],          # bounded: long campaigns stay small
            "facts": slim(graph.facts.values()),
        }
        fd, tmp = tempfile.mkstemp(dir=str(d), suffix=".tmp")
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh)
        os.replace(tmp, d / "live.json")      # atomic: readers never see a partial file
        page = d / "live.html"
        if not page.exists():
            page.write_text(HTML)
    except Exception:  # noqa: BLE001 - monitoring must never break the run
        pass


HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>DRIFT - live memory</title><style>
*{box-sizing:border-box}
body{margin:0;background:#0f1117;color:#e6e9f0;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
header{padding:11px 18px;border-bottom:1px solid #232838;display:flex;gap:20px;align-items:center;flex-wrap:wrap}
h1{font-size:15px;margin:0;font-weight:600}
#meta{color:#9aa4bd}
.dot{width:8px;height:8px;border-radius:50%;background:#2a9d8f;display:inline-block;margin-right:6px;animation:pulse 1.4s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
.stale .dot{background:#6e7794;animation:none}
#bar{height:3px;background:#1d2231}#fill{height:100%;background:#2a9d8f;width:0;transition:width .4s}
#wrap{display:flex;height:calc(100vh - 62px)}
#g{flex:1;overflow:hidden}svg{width:100%;height:100%;display:block}
text{fill:#8f98b2;font-size:9px;pointer-events:none}
.act{stroke:#2a9d8f;opacity:.75;stroke-width:1.4}
.inv{stroke:#c94f5e;stroke-dasharray:4 3;stroke-width:2}
.pru{stroke:#39405a;opacity:.3;stroke-dasharray:1 4}
#side{width:330px;background:#12151f;border-left:1px solid #232838;overflow-y:auto;padding:13px 15px}
.stat{display:flex;gap:15px;flex-wrap:wrap;margin-bottom:13px;padding-bottom:12px;border-bottom:1px solid #232838}
.stat div{font-size:11px;color:#6e7794}.stat b{display:block;font-size:17px;color:#e6e9f0;font-variant-numeric:tabular-nums}
h2{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6e7794;margin:0 0 9px}
.ev{padding:6px 8px;margin-bottom:5px;border-radius:5px;background:#181c26;border-left:3px solid #2a9d8f;font-size:12px}
.ev.i{border-left-color:#c94f5e}
</style></head><body>
<header><h1><span class="dot" id="dot"></span>DRIFT · live memory</h1><div id="meta">waiting for live.json…</div></header>
<div id="bar"><div id="fill"></div></div>
<div id="wrap"><div id="g"><svg id="svg" viewBox="0 0 900 700" preserveAspectRatio="xMidYMid meet"></svg></div>
<div id="side"><div class="stat" id="stat"></div><h2>Newest facts</h2><div id="log"></div></div></div>
<script>
const esc=s=>String(s).replace(/[<>&"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c]));
let pos={}, lastSession=-1, misses=0;

function layout(nodes,edges){
  // Existing entities keep their coordinates; only newcomers are seeded and the
  // system is relaxed briefly. Re-solving from scratch each poll would make the
  // map jump every few seconds and hide the thing you are watching for.
  nodes.forEach((n,i)=>{ if(!pos[n.id]) pos[n.id]={x:450+Math.cos(i*2.4)*(70+7*i%330),y:350+Math.sin(i*2.4)*(55+5*i%260),vx:0,vy:0}; });
  const P=pos;
  for(let it=0;it<40;it++){
    nodes.forEach(a=>{ const A=P[a.id];
      nodes.forEach(b=>{ if(a===b)return; const B=P[b.id];
        let dx=A.x-B.x,dy=A.y-B.y,d2=dx*dx+dy*dy+.01,f=900/d2;
        A.vx+=dx*f/Math.sqrt(d2); A.vy+=dy*f/Math.sqrt(d2); });
      A.vx+=(450-A.x)*.003; A.vy+=(350-A.y)*.003; });
    edges.forEach(e=>{ const a=P[e.s],b=P[e.o]; if(!a||!b)return;
      const dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+.01,f=(d-95)*.012;
      a.vx+=dx/d*f; a.vy+=dy/d*f; b.vx-=dx/d*f; b.vy-=dy/d*f; });
    nodes.forEach(n=>{ const A=P[n.id]; A.x+=A.vx*=.55; A.y+=A.vy*=.55;
      A.x=Math.max(26,Math.min(874,A.x)); A.y=Math.max(22,Math.min(678,A.y)); });
  }
}

function render(d){
  const nodes={}, edges=[];
  d.facts.forEach(f=>{
    const s=(f.subject||'?').trim().toLowerCase(), o=(f.object||'?').trim().toLowerCase();
    [[s,f.subject],[o,f.object]].forEach(([k,lab])=>{ if(!nodes[k])nodes[k]={id:k,label:(lab||'?').trim(),deg:0}; nodes[k].deg++; });
    edges.push({s,o,txt:f.text,cls:!f.active?'pru':(f.t_invalid_at?'inv':'act'),t:f.t_ingested});
  });
  const ns=Object.values(nodes);
  layout(ns,edges);
  const live={}; edges.forEach(e=>{ if(e.cls!=='pru'){live[e.s]=1;live[e.o]=1;} });
  document.getElementById('svg').innerHTML =
    edges.map(e=>{const a=pos[e.s],b=pos[e.o]; if(!a||!b)return '';
      return `<line class="${e.cls}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"><title>${esc(e.txt)}</title></line>`}).join('')
    + ns.filter(n=>live[n.id]).map(n=>{const p=pos[n.id];
      return `<g><circle cx="${p.x}" cy="${p.y}" r="${3.5+Math.min(9,n.deg)}" fill="#2a9d8f" opacity=".82"><title>${esc(n.label)}</title></circle>`
        + (n.deg>2?`<text x="${p.x+8}" y="${p.y+3}">${esc(n.label).slice(0,26)}</text>`:'')+`</g>`}).join('');

  const s=d.stats||{};
  document.getElementById('stat').innerHTML =
    `<div>ACTIVE<b>${s.active_facts??'–'}</b></div><div>SUPERSEDED<b>${s.invalidated_active??'–'}</b></div>
     <div>PRUNED<b>${s.pruned??'–'}</b></div><div>REJECTED<b>${s.write_rejections??0}</b></div>`;
  document.getElementById('meta').textContent =
    `${d.policy} · ${(d.model||'').split('/').pop()} · ${d.conversation} · session ${d.session+1}/${d.n_sessions}`;
  document.getElementById('fill').style.width = (100*(d.session+1)/Math.max(d.n_sessions,1))+'%';

  const newest=[...d.facts].sort((a,b)=>b.t_ingested-a.t_ingested).slice(0,14);
  document.getElementById('log').innerHTML = newest.map(f=>
    `<div class="ev ${f.t_invalid_at?'i':''}">${esc(f.text)}${f.t_invalid_at?'<br><span style="color:#c94f5e">superseded</span>':''}</div>`).join('');
}

async function poll(){
  try{
    const r=await fetch('live.json?t='+Date.now(),{cache:'no-store'});
    const d=await r.json();
    if(d.session!==lastSession){ lastSession=d.session; misses=0; document.body.classList.remove('stale'); }
    else if(++misses>8){ document.body.classList.add('stale');
      document.getElementById('meta').textContent+=' · run finished or paused'; }
    render(d);
  }catch(e){ /* file not written yet, or mid-rename: try again */ }
}
poll(); setInterval(poll,1500);
</script></body></html>"""
