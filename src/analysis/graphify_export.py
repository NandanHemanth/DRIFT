"""Export DRIFT memory snapshots as Graphify/NetworkX-compatible graphs.

Bridges DRIFT (bitemporal agent memory) and Graphify-style tooling
(graphify.net): entity co-occurrence graph in standard node-link JSON,
community labels, god-node (degree) analytics, and an optional standalone
interactive HTML view. Output loads directly into NetworkX
(`nx.node_link_graph`), Gephi, or any node-link consumer; run Graphify's own
pipeline over the export directory for its full report.

Usage:
    python analysis/graphify_export.py results/swarm_smoke/shared__P2.json
    python analysis/graphify_export.py results/swarm_smoke/shared__P2.json --html
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def facts_to_graph(facts: list[dict]) -> dict:
    """Entity co-occurrence graph. Nodes = entities (+degree, community);
    edges = facts (predicate, active/invalidated status, provenance, times)."""
    nodes: dict[str, dict] = {}
    edges = []
    for f in facts:
        s, o = f["subject"].lower().strip(), f["object"].lower().strip()
        for ent in (s, o):
            if ent not in nodes:
                nodes[ent] = {"id": ent, "label": ent, "degree": 0}
        nodes[s]["degree"] += 1
        nodes[o]["degree"] += 1
        edges.append({
            "source": s, "target": o, "label": f["predicate"],
            "text": f["text"], "active": f.get("active", True),
            "invalidated": f.get("t_invalid_at") is not None,
            "provenance": f.get("provenance", ""),
            "t_valid_start": f.get("t_valid_start"),
            "t_invalid_at": f.get("t_invalid_at"),
        })
    # community labels via label propagation (mirrors P5's clustering)
    neigh: dict[str, set[str]] = {n: set() for n in nodes}
    for e in edges:
        neigh[e["source"]].add(e["target"])
        neigh[e["target"]].add(e["source"])
    label = {n: i for i, n in enumerate(sorted(nodes))}
    for _ in range(10):
        changed = False
        for n in neigh:
            if not neigh[n]:
                continue
            counts: dict[int, int] = {}
            for m in neigh[n]:
                counts[label[m]] = counts.get(label[m], 0) + 1
            best = min(k for k, v in counts.items() if v == max(counts.values()))
            if best < label[n]:
                label[n], changed = best, True
        if not changed:
            break
    communities = sorted(set(label.values()))
    remap = {c: i for i, c in enumerate(communities)}
    for n in nodes.values():
        n["community"] = remap[label[n["id"]]]
    god_nodes = sorted(nodes.values(), key=lambda n: n["degree"], reverse=True)[:5]
    return {
        "directed": True, "multigraph": True,
        "graph": {"name": "drift_memory", "n_communities": len(communities),
                  "god_nodes": [n["id"] for n in god_nodes]},
        "nodes": sorted(nodes.values(), key=lambda n: -n["degree"]),
        "links": edges,
    }


HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>DRIFT memory graph</title>
<style>body{margin:0;background:#0f1117;color:#e6e9f0;font:13px sans-serif}
svg{width:100vw;height:100vh}text{fill:#e6e9f0;font-size:10px}
.inv{stroke:#c94f5e;stroke-dasharray:4 3}.act{stroke:#4a5268}circle{cursor:grab}
#info{position:fixed;top:10px;left:10px;background:#181c26;padding:10px 14px;border-radius:8px;max-width:380px}</style>
</head><body><div id="info"><b>DRIFT memory graph</b><br><span id="detail">hover a node/edge · red dashed = invalidated fact</span></div>
<svg id="s"></svg><script>
const G = __GRAPH__;
const W=innerWidth,H=innerHeight,N=G.nodes,L=G.links;
const idx={};N.forEach((n,i)=>{idx[n.id]=i;n.x=W/2+Math.cos(i*2.4)*(80+8*i);n.y=H/2+Math.sin(i*2.4)*(60+6*i);n.vx=0;n.vy=0});
const colors=['#2a9d8f','#e07b39','#7b6fb0','#c94f5e','#8888aa','#5aa9e6','#f4a261','#90be6d'];
function tick(){for(let k=0;k<3;k++){N.forEach(a=>{N.forEach(b=>{if(a===b)return;let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+0.01,f=1200/d2;a.vx+=dx*f/Math.sqrt(d2);a.vy+=dy*f/Math.sqrt(d2)});a.vx+=(W/2-a.x)*0.002;a.vy+=(H/2-a.y)*0.002});
L.forEach(l=>{const a=N[idx[l.source]],b=N[idx[l.target]];const dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+0.01,f=(d-110)*0.01;a.vx+=dx/d*f;a.vy+=dy/d*f;b.vx-=dx/d*f;b.vy-=dy/d*f});
N.forEach(n=>{n.x+=n.vx*=0.6;n.y+=n.vy*=0.6;n.x=Math.max(20,Math.min(W-20,n.x));n.y=Math.max(20,Math.min(H-20,n.y))})}render()}
function render(){const svg=document.getElementById('s');svg.innerHTML=L.map(l=>{const a=N[idx[l.source]],b=N[idx[l.target]];
return `<line class="${l.invalidated?'inv':'act'}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"><title>${l.label}: ${l.text}</title></line>`}).join('')+
N.map(n=>`<g><circle cx="${n.x}" cy="${n.y}" r="${5+Math.min(12,n.degree)}" fill="${colors[n.community%colors.length]}"><title>${n.id} (degree ${n.degree}, community ${n.community})</title></circle>
<text x="${n.x+9}" y="${n.y+3}">${n.label}</text></g>`).join('')}
for(let i=0;i<160;i++)tick();setInterval(tick,50);
document.getElementById('detail').textContent=`${N.length} entities · ${L.length} facts · ${G.graph.n_communities} communities · god nodes: ${G.graph.god_nodes.join(', ')}`;
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DRIFT memory as a Graphify-style graph")
    parser.add_argument("result_json", help="a result cell JSON containing graph_snapshot")
    parser.add_argument("--html", action="store_true", help="also write interactive HTML")
    parser.add_argument("-o", "--out", default=None)
    args = parser.parse_args()

    data = json.loads(Path(args.result_json).read_text())
    facts = data.get("graph_snapshot")
    if not facts:
        raise SystemExit("no graph_snapshot in this result file - rerun the experiment "
                         "with \"save_graph\": true in the config")
    graph = facts_to_graph(facts)
    out = Path(args.out) if args.out else Path(args.result_json).with_suffix(".graph.json")
    out.write_text(json.dumps(graph, indent=1))
    print(f"graph -> {out}  ({len(graph['nodes'])} entities, {len(graph['links'])} facts, "
          f"{graph['graph']['n_communities']} communities; god nodes: "
          f"{', '.join(graph['graph']['god_nodes'])})")
    if args.html:
        html_out = out.with_suffix(".html")
        html_out.write_text(HTML.replace("__GRAPH__", json.dumps(graph)))
        print(f"interactive -> {html_out}")


if __name__ == "__main__":
    main()
