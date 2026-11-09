"""Soundness and completeness of each forgetting policy, from the saved final-run graphs.

For every question whose fact changed, look at the memory at the end of the run:
  complete = the old value is no longer visible to retrieval (hidden or deleted)
  sound    = the current value is still visible (not refused, hidden or deleted)
"Visible" means active and, for P2, not closed. A fact belongs to a question's slot
when it contains the value and its other end (subject or object) appears in the
question. Averaged over the five answer models. No model is called.

Output: paper/tables_final/forgetting_correctness.csv
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["anthropic_claude-sonnet-5.5", "openai_gpt-6.1-sol", "google_gemini-3.8-flash",
          "meta-llama_llama-3.1-8b-instruct", "qwen_qwen3-14b"]
BENCH = {"MQuAKE-T": ("final_mquake_t", "data/mquake_t_sh.json"),
         "FactConsolidation": ("final_factconsolidation", "data/factconsolidation_sh_6k.json")}
POLICIES = ["P0", "P1", "P2", "P3", "P4", "P5"]


def slot(fact, value, question):
    text, q = fact["text"].lower(), question.lower()
    if value not in text:
        return False
    s, o = fact["subject"].lower().strip(), fact["object"].lower().strip()
    other = s if value in o else o
    return len(other) > 2 and other in q


def graphs(d, pol, model, data):
    r = json.loads((ROOT / f"artifacts/results/{d}/{pol}__openrouter_{model}.json").read_text())
    return r.get("graph_snapshots") or {data["conversations"][0]["id"]: r["graph_snapshot"]}


def main():
    rows = []
    for bench, (d, ds) in BENCH.items():
        data = json.loads((ROOT / ds).read_text())
        qs = [(c["id"], q) for c in data["conversations"] for q in c["questions"] if q.get("stale_answer")]
        for pol in POLICIES:
            n_old = vis_old = n_cur = vis_cur = 0
            for m in MODELS:
                ref, g = graphs(d, "P0", m, data), graphs(d, pol, m, data)
                for cid, q in qs:
                    cur = (q.get("current_answer") or q["answer"]).lower()
                    old = q["stale_answer"].lower()
                    visible = [f for f in g[cid] if f.get("active", True)
                               and not (pol == "P2" and f.get("t_invalid_at"))]
                    if any(slot(f, old, q["question"]) for f in ref[cid]):
                        n_old += 1
                        vis_old += any(slot(f, old, q["question"]) and cur not in f["text"].lower()
                                       for f in visible)
                    if any(slot(f, cur, q["question"]) for f in ref[cid]):
                        n_cur += 1
                        vis_cur += any(slot(f, cur, q["question"]) for f in visible)
            rows.append([bench, pol, n_old // len(MODELS), n_cur // len(MODELS),
                         f"{1 - vis_old / n_old:.3f}", f"{vis_cur / n_cur:.3f}"])
            print(*rows[-1])
    out = ROOT / "paper/tables_final/forgetting_correctness.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["benchmark", "policy", "questions with old value stored",
                    "questions with current value stored", "completeness", "soundness"])
        w.writerows(rows)
    print("wrote", out)


if __name__ == "__main__":
    main()
