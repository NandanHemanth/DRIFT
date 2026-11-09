"""Self-contained interactive dashboard of the final campaign.

Reads artifacts/final_results.json and paper/figures_final/*.png and writes
paper/FINAL_RESULTS_DASHBOARD.html: one file, no network, opens in any browser.

Usage:
    python scripts/build_final_dashboard.py
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "paper/figures_final"

FIGS = [
    ("F01_headline_accuracy_staleness.png", "Accuracy and staleness by policy, averaged over the five answer models"),
    ("F02_p0_vs_p2_by_model.png", "Append-only (P0) against bitemporal invalidation (P2), per model"),
    ("F03_mechanism_exposure_reading_error.png", "Why staleness happens: old value in the prompt, and how often each model repeats it"),
    ("F04_tokens_and_cost.png", "Prompt tokens per policy, and USD per 1,000 correct answers under P2"),
    ("F05_gain_by_model_tier.png", "Accuracy gained by P2 over P0, by model tier"),
    ("F06_rq3_p2_vs_p5.png", "RQ3: bitemporal P2 against time-blind topology P5"),
    ("F07_rq4_topologies.png", "RQ4: several agents sharing memory"),
    ("F08_grace_tradeoff.png", "Grace period: current and history questions against facts stored"),
    ("F09_substrate_matching.png", "Contradiction detection: exact, normalised, LLM"),
    ("F10_heldout_weights.png", "Retrieval weights on a benchmark the search never saw"),
    ("F11_cost_accuracy_scatter.png", "Every policy and model: prompt tokens against accuracy"),
    ("F12_detection_and_p4.png", "Detection coverage, and what LLM consolidation deletes"),
    ("rank_agreement_accuracy.png", "Agreement of policy rankings across model and benchmark (accuracy)"),
]


def img64(path: Path) -> str:
    try:
        from PIL import Image
        im = Image.open(path)
        im.thumbnail((1500, 1500))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "PNG", optimize=True)
        data = buf.getvalue()
    except Exception:  # noqa: BLE001
        data = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode()


def main() -> None:
    R = json.loads((ROOT / "artifacts/final_results.json").read_text())
    for k in ("correct", "stale"):
        R["ranks"][k].pop("spearman", None)
    figs = [{"src": img64(FIG / f), "cap": c} for f, c in FIGS if (FIG / f).is_file()]
    html = TEMPLATE.replace("__DATA__", json.dumps(R)).replace("__FIGS__", json.dumps(figs))
    out = ROOT / "paper/FINAL_RESULTS_DASHBOARD.html"
    out.write_text(html)
    print("wrote", out, f"({out.stat().st_size / 1e6:.1f} MB)")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DRIFT final campaign: results dashboard</title>
<style>
:root{--teal:#0F766E;--rust:#B5523B;--ink:#1F2933;--mute:#7B8794;--panel:#F7F8F9;--line:#E4E7EB}
*{box-sizing:border-box}body{margin:0;font-family:Calibri,'Segoe UI',Arial,sans-serif;color:var(--ink);background:#fff}
header{padding:28px 40px 18px;border-bottom:1px solid var(--line)}h1{margin:0;font-size:26px}
header p{margin:6px 0 0;color:var(--mute)}
nav{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);padding:8px 40px;z-index:5;display:flex;gap:18px;flex-wrap:wrap}
nav a{color:var(--teal);text-decoration:none;font-size:14px}
section{padding:22px 40px;border-bottom:1px solid var(--line)}h2{font-size:20px;margin:0 0 6px}
.note{color:var(--mute);font-size:13px;margin:0 0 12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.kpi{background:var(--panel);border-radius:8px;padding:14px 16px}.kpi b{display:block;font-size:26px;color:var(--teal)}
.kpi span{font-size:13px;color:var(--mute)}
.controls{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:12px;align-items:center}
select{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;font-size:13px;width:100%}th,td{border:1px solid var(--line);padding:6px 8px;text-align:center}
th{background:var(--panel);cursor:pointer}td:first-child,th:first-child{text-align:left}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}@media(max-width:1000px){.grid2{grid-template-columns:1fr}}
figure{margin:0 0 22px}figure img{width:100%;border:1px solid var(--line);border-radius:6px}figcaption{font-size:13px;color:var(--mute);margin-top:4px}
.sig{color:var(--teal);font-weight:bold}.neg{color:var(--rust);font-weight:bold}
svg text{font-family:Calibri,Arial,sans-serif}
</style></head><body>
<header><h1>DRIFT final campaign: results</h1>
<p>Five answer models x seven forgetting policies x three benchmarks, plus RQ4, grace period, matching ablation and held-out weights. Every number is recomputed from saved per-question records.</p></header>
<nav><a href="#kpi">Overview</a><a href="#explore">Explorer</a><a href="#pairs">Significance</a><a href="#tiers">Small vs frontier</a>
<a href="#rq4">RQ4</a><a href="#grace">Grace</a><a href="#sub">Matching</a><a href="#weights">Weights</a><a href="#figs">All figures</a></nav>

<section id="kpi"><h2>Overview</h2><p class="note">Averages over the five answer models. P0 = append-only, P2 = bitemporal contradiction invalidation.</p>
<div class="kpis" id="kpis"></div></section>

<section id="explore"><h2>Explorer</h2><p class="note">Pick a benchmark and a metric. Cells are coloured from worst (light) to best (teal). Click a policy row to plot it across models.</p>
<div class="controls"><label>Benchmark <select id="bsel"></select></label><label>Metric <select id="msel"></select></label></div>
<div class="grid2"><div id="heat"></div><div><svg id="bar" width="100%" height="320"></svg></div></div></section>

<section id="pairs"><h2>P2 against every other policy</h2><p class="note">Per question, paired. Interval: paired bootstrap 95%. p: exact McNemar, Holm-corrected within each scope. W/L: questions P2 got right and the other policy wrong, and the reverse.</p>
<div class="controls"><label>Benchmark <select id="psel"></select></label><label>Scope <select id="ssel"></select></label></div><div id="ptab"></div></section>

<section id="tiers"><h2>Who benefits from forgetting</h2><p class="note">Mean per-question change from P0 to P2, grouped by model tier.</p><div id="ttab"></div></section>

<section id="rq4"><h2>RQ4: several agents, one memory (MQuAKE-T)</h2><p class="note">Every answering role is Gemini 3.8 Flash so only the memory differs. Shared: five different models write one memory. Independent: each agent keeps its own memory from 80% of the sessions. Orchestrator: one memory, a router picks a specialist.</p><div id="rq4tab"></div></section>

<section id="grace"><h2>Grace period with history questions</h2><p class="note">History accuracy = answering "what was it before the last change". Small models; P2 deletes a closed fact after the grace period.</p>
<div class="controls"><label>Benchmark <select id="gsel"></select></label></div><div class="grid2"><div id="gtab"></div><svg id="gsvg" width="100%" height="300"></svg></div></section>

<section id="sub"><h2>How contradictions are detected</h2><p class="note">P2 with exact relation names, normalised names (main run), or an LLM check (as in Zep). Small models.</p><div id="subtab"></div></section>

<section id="weights"><h2>Retrieval weights on an unseen benchmark</h2><p class="note">FactConsolidation, P2. The search that chose the alternatives never saw this benchmark.</p><div id="wtab"></div></section>

<section id="figs"><h2>All figures</h2><div id="gallery"></div></section>

<script>
const R=__DATA__, FIGS=__FIGS__;
const L=m=>(R.models[m]||{}).label||m.split('/').pop();
const f3=v=>v==null?'n/a':(+v).toFixed(3), f2=v=>v==null?'n/a':(+v).toFixed(2);
const pfmt=p=>p==null?'':(p<0.001?'<0.001':p.toFixed(3));
function el(t,a={},h=''){const e=document.createElement(t);for(const k in a)e.setAttribute(k,a[k]);e.innerHTML=h;return e}
function tbl(head,rows){let h='<table><tr>'+head.map(x=>'<th>'+x+'</th>').join('')+'</tr>';
 rows.forEach(r=>h+='<tr>'+r.map(x=>'<td>'+x+'</td>').join('')+'</tr>');return h+'</table>'}
function sortable(div){div.querySelectorAll('th').forEach((th,i)=>th.onclick=()=>{const t=th.closest('table');
 const rows=[...t.querySelectorAll('tr')].slice(1);const asc=th.dataset.a!=='1';th.dataset.a=asc?'1':'0';
 rows.sort((a,b)=>{const x=a.children[i].innerText,y=b.children[i].innerText;const nx=parseFloat(x.replace(/[^\d.+-]/g,'')),ny=parseFloat(y.replace(/[^\d.+-]/g,''));
 return (isNaN(nx)||isNaN(ny)?x.localeCompare(y):nx-ny)*(asc?1:-1)});rows.forEach(r=>t.appendChild(r))})}

// KPIs
(function(){const k=document.getElementById('kpis');const B=R.benchmarks;
 const add=(big,small)=>k.appendChild(el('div',{class:'kpi'},'<b>'+big+'</b><span>'+small+'</span>'));
 ['MQuAKE-T','FactConsolidation','ConvoMem'].forEach(b=>{const a=B[b].policy_avg;
  add(f2(a.P0.accuracy)+' &rarr; '+f2(a.P2.accuracy),b+': accuracy, P0 to P2');
  add(f3(a.P0.staleness)+' &rarr; '+f3(a.P2.staleness),b+': staleness, P0 to P2')});
 const j=R.judge;add((100*j.agreement).toFixed(1)+'%','judge agreement with Claude Sonnet 5.5 (kappa '+f2(j.kappa)+')');
 add(f2(R.ranks.correct_no_convomem),"Kendall's W, policy ranking by accuracy (MQuAKE-T + FactConsolidation, 10 model-benchmark pairs)")})();

// Explorer
const METRICS={accuracy:['accuracy',1],staleness:['staleness',-1],prompt_tokens:['prompt tokens per question',-1],
 usd_per_1k_correct:['USD per 1,000 correct answers',-1],mentions_old:['answers mentioning the old value',0],
 closed_in_context:['closed facts among the 25 retrieved',-1],facts_active:['facts stored',-1],f1:['token F1',1]};
const bsel=document.getElementById('bsel'),msel=document.getElementById('msel');
Object.keys(R.benchmarks).forEach(b=>bsel.appendChild(el('option',{value:b},b)));
Object.entries(METRICS).forEach(([k,v])=>msel.appendChild(el('option',{value:k},v[0])));
let selPol='P2';
function explore(){const B=R.benchmarks[bsel.value],m=msel.value,dir=METRICS[m][1];
 const vals=[];B.policies.forEach(p=>B.models.forEach(md=>{const c=B.cells[p+'|'+md];if(c&&c[m]!=null)vals.push(c[m])}));
 const lo=Math.min(...vals),hi=Math.max(...vals);
 let h='<table><tr><th>policy</th>'+B.models.map(md=>'<th>'+L(md)+'</th>').join('')+'<th>mean</th></tr>';
 B.policies.forEach(p=>{h+='<tr data-p="'+p+'" style="cursor:pointer"><td><b>'+p+'</b></td>';
  B.models.forEach(md=>{const c=B.cells[p+'|'+md];const v=c?c[m]:null;let t=v==null?0:(v-lo)/((hi-lo)||1);if(dir<0)t=1-t;if(dir===0)t=0.5;
   const bg=v==null?'#fff':'rgba(15,118,110,'+(0.08+0.6*t).toFixed(2)+')';
   let txt=v==null?'n/a':(m==='usd_per_1k_correct'?'$'+f2(v):(m.includes('tokens')||m==='facts_active'?Math.round(v):f3(v)));
   if(c&&m==='accuracy')txt+='<br><span style="color:#7B8794;font-size:11px">['+f2(c.acc_lo)+', '+f2(c.acc_hi)+']</span>';
   h+='<td style="background:'+bg+'">'+txt+'</td>'});
  const a=B.policy_avg[p]&&B.policy_avg[p][m];h+='<td>'+(a==null?'':(m.includes('tokens')||m==='facts_active'?Math.round(a):f3(a)))+'</td></tr>'});
 document.getElementById('heat').innerHTML=h+'</table>';
 document.querySelectorAll('#heat tr[data-p]').forEach(r=>r.onclick=()=>{selPol=r.dataset.p;bar()});bar()}
function bar(){const B=R.benchmarks[bsel.value],m=msel.value,svg=document.getElementById('bar');svg.innerHTML='';
 const W=svg.clientWidth||600,H=300,pad=40,vals=B.models.map(md=>(B.cells[selPol+'|'+md]||{})[m]||0),mx=Math.max(...vals,1e-9)*1.15;
 const bw=(W-2*pad)/vals.length*0.6;svg.innerHTML+='<text x="'+pad+'" y="16" font-size="13" font-weight="bold">'+selPol+': '+METRICS[m][0]+'</text>';
 vals.forEach((v,i)=>{const x=pad+i*(W-2*pad)/vals.length+bw*0.3,h=(H-70)*v/mx,y=H-40-h;
  svg.innerHTML+='<rect x="'+x+'" y="'+y+'" width="'+bw+'" height="'+h+'" fill="#0F766E"></rect>';
  svg.innerHTML+='<text x="'+(x+bw/2)+'" y="'+(y-4)+'" font-size="11" text-anchor="middle">'+(m.includes('tokens')||m==='facts_active'?Math.round(v):(+v).toFixed(3))+'</text>';
  svg.innerHTML+='<text x="'+(x+bw/2)+'" y="'+(H-22)+'" font-size="11" text-anchor="middle">'+L(B.models[i])+'</text>'});
 svg.innerHTML+='<line x1="'+pad+'" x2="'+(W-pad)+'" y1="'+(H-40)+'" y2="'+(H-40)+'" stroke="#C9CED4"></line>'}
bsel.onchange=explore;msel.onchange=explore;window.addEventListener('resize',bar);explore();

// Pairwise
const psel=document.getElementById('psel'),ssel=document.getElementById('ssel');
Object.keys(R.pairwise).forEach(b=>psel.appendChild(el('option',{value:b},b)));
function pairs(){const pw=R.pairwise[psel.value];const scopes=[...new Set(pw.map(x=>x.scope))];
 const cur=ssel.value;ssel.innerHTML='';scopes.forEach(s=>ssel.appendChild(el('option',{value:s},s==='pooled'?'all models pooled':L(s))));
 if(scopes.includes(cur))ssel.value=cur;
 const rows=pw.filter(x=>x.scope===ssel.value).map(x=>{const cls=(lo,hi,p)=>p<0.05?(lo>0?'sig':hi<0?'neg':''):'';
  return ['P2 vs '+x.vs,'<span class="'+cls(x.acc_lo,x.acc_hi,x.p_acc_holm)+'">'+(x.acc_diff>=0?'+':'')+f3(x.acc_diff)+'</span> ['+f3(x.acc_lo)+', '+f3(x.acc_hi)+']',
  pfmt(x.p_acc_holm),x.p2_wins+' / '+x.p2_losses,
  '<span class="'+cls(-x.stale_hi,-x.stale_lo,x.p_stale_holm)+'">'+(x.stale_diff>=0?'+':'')+f3(x.stale_diff)+'</span> ['+f3(x.stale_lo)+', '+f3(x.stale_hi)+']',pfmt(x.p_stale_holm)]});
 const d=document.getElementById('ptab');d.innerHTML=tbl(['comparison','accuracy difference [95% CI]','p (Holm)','P2 wins / losses','staleness difference [95% CI]','p (Holm)'],rows)}
psel.onchange=pairs;ssel.onchange=pairs;pairs();

// Tiers
(function(){const rows=[];Object.entries(R.tiers).forEach(([b,t])=>['frontier','mid','small'].forEach(k=>{if(t[k])rows.push([b,k,(t[k].acc_gain>=0?'+':'')+f3(t[k].acc_gain),(t[k].stale_reduction>=0?'+':'')+f3(t[k].stale_reduction),t[k].n])}));
 const d=document.getElementById('ttab');d.innerHTML=tbl(['benchmark','tier','accuracy gain P0 to P2','staleness removed','paired answers'],rows);sortable(d)})();

// RQ4
(function(){const order=['NOMEM','P0','P1','P2','P3','P4','P5'];const rows=R.rq4.slice().sort((a,b)=>(a.topology+a.matching).localeCompare(b.topology+b.matching)||order.indexOf(a.policy)-order.indexOf(b.policy))
 .map(x=>[x.topology,x.matching,x.policy,f3(x.accuracy),f3(x.staleness),Math.round(x.tokens||0),x.closed==null?'n/a':x.closed,x.cross_writer==null?'n/a':x.cross_writer]);
 const d=document.getElementById('rq4tab');d.innerHTML=tbl(['topology','matching','policy','accuracy','staleness','tokens / q','facts closed','closed by another writer'],rows);sortable(d)})();

// Grace
const gsel=document.getElementById('gsel');Object.keys(R.grace).forEach(b=>gsel.appendChild(el('option',{value:b},b)));
function grace(){const rows=R.grace[gsel.value];const ms=Object.keys(rows[0]).filter(k=>k.startsWith('openrouter'));
 const head=['grace (days)','facts stored','old value still stored'].concat(...ms.map(m=>[L(m)+' current',L(m)+' history']));
 document.getElementById('gtab').innerHTML=tbl(head,rows.map(r=>[r.grace,r.facts,f2(r.old_stored)].concat(...ms.map(m=>[f2(r[m].current),f2(r[m].history)]))));
 const svg=document.getElementById('gsvg');svg.innerHTML='';const W=svg.clientWidth||600,H=290,p=40,n=rows.length;
 const X=i=>p+i*(W-2*p)/(n-1),Y=v=>H-35-(H-60)*v;const cols=['#B5523B','#0F766E'];
 ms.forEach((m,k)=>['history','current'].forEach((key,j)=>{let d='';rows.forEach((r,i)=>d+=(i?'L':'M')+X(i)+' '+Y(r[m][key]));
  svg.innerHTML+='<path d="'+d+'" fill="none" stroke="'+cols[k]+'" stroke-width="2" '+(j?'stroke-dasharray="4 3"':'')+'></path>'}));
 rows.forEach((r,i)=>svg.innerHTML+='<text x="'+X(i)+'" y="'+(H-14)+'" font-size="11" text-anchor="middle">'+r.grace+'</text>');
 svg.innerHTML+='<text x="'+p+'" y="14" font-size="12">solid = history accuracy, dashed = current accuracy; red '+L(ms[0])+', teal '+L(ms[1])+'</text>'}
gsel.onchange=grace;grace();window.addEventListener('resize',grace);

// Substrate and weights
(function(){const rows=R.substrate.slice().sort((a,b)=>(a.benchmark+a.model+a.mode).localeCompare(b.benchmark+b.model+b.mode)).map(x=>[x.benchmark,L(x.model),x.mode,f3(x.accuracy),f3(x.staleness),x.closed,x.llm_checks]);
 const d=document.getElementById('subtab');d.innerHTML=tbl(['benchmark','model','matching','accuracy','staleness','facts closed','LLM checks'],rows);sortable(d);
 const nm={w631:'0.6/0.3/0.1 (published)',w912:'0.9/0.1/0.2 (MQuAKE-T best)',w811:'0.8/0.1/0.1 (ConvoMem best)'};
 const w=R.heldout.map(x=>[L(x.model),nm[x.weights],f3(x.accuracy),f3(x.staleness),x.better==null?'-':x.better+' / '+x.worse,x.p==null?'-':pfmt(x.p)]);
 document.getElementById('wtab').innerHTML=tbl(['model','weighting','accuracy','staleness','better / worse than published','McNemar p'],w)})();

// Gallery
(function(){const g=document.getElementById('gallery');FIGS.forEach(f=>g.appendChild(el('figure',{},'<img src="'+f.src+'" alt="'+f.cap+'"><figcaption>'+f.cap+'</figcaption>')))})();
</script></body></html>
"""

if __name__ == "__main__":
    main()
