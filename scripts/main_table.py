"""The merged main table (2026-10-20): baselines, ablations, ours; one cell per
model = verdict accuracy with macro precision / recall / F1 over the three verdict classes."""
import json, random
from pathlib import Path
R = Path("results"); E = Path("/home/henryhcy/ehragent_baseline")
MODELS = [("q25pair", "Qwen2.5-32B pair"), ("qwen38_27b", "qwen3.8-27B"), ("gemma4_31b", "gemma4-31B"), ("opus", "Opus 5.5"), ("gpt", "GPT-5.6")]
CLASSES = ("supported", "refuted", "insufficient")

def prf_from_pairs(pairs):
    acc = sum(1 for g, p in pairs if g == p) / len(pairs)
    P = R_ = F = []; Ps, Rs, Fs = [], [], []
    for c in CLASSES:
        tp = sum(1 for g, p in pairs if g == c and p == c); fp = sum(1 for g, p in pairs if g != c and p == c); fn = sum(1 for g, p in pairs if g == c and p != c)
        pr = tp / (tp + fp) if tp + fp else 0.0; rc = tp / (tp + fn) if tp + fn else 0.0
        Ps.append(pr); Rs.append(rc); Fs.append(2 * pr * rc / (pr + rc) if pr + rc else 0.0)
    return acc, sum(Ps) / 3, sum(Rs) / 3, sum(Fs) / 3

def cell_metrics(run):
    p = R / run / "metrics.json"
    if not p.exists(): return None
    m = json.loads(p.read_text()); v = m["verdict"]; pc = v["per_class"]
    return (v["accuracy"], sum(pc[c]["precision"] or 0 for c in CLASSES) / 3, sum(pc[c]["recall"] or 0 for c in CLASSES) / 3, v["class_macro_f1"])

def fmt(t, bold=False):
    if t is None: return "---"
    a, p, r, f = t
    s = f"{a:.3f}" + (f"\\,{{\\scriptsize({p:.3f}/{r:.3f}/{f:.3f})}}")
    return f"\\textbf{{{s}}}" if bold else s

gold = json.load(open(E / "medtempo_data/gold_map_test_cohort_v1.2.json"))
def ehr(path):
    rows = [json.loads(l) for l in open(path)]
    return prf_from_pairs([(gold[r["id"]]["gold_verdict"], r.get("pred_raw") or "none") for r in rows])
def veritas():
    rows = json.load(open("/home/henryhcy/veritas_baseline/runs/scored_D.json"))
    return prf_from_pairs([(r["gold"], r["eco"]) for r in rows])

rows = []
def row(label, cells, bold=False): rows.append(label + " & " + " & ".join(fmt(c, bold) for c in cells) + " \\\\")
rows.append("\\multicolumn{6}{@{}l}{\\textit{baselines}} \\\\")
row("EHRSQL, schema only", [cell_metrics(f"test_{k}_cellA") for k, _ in MODELS])
row("EHRSQL + codebook", [cell_metrics(f"test_{k}_cellB") for k, _ in MODELS])
ehr_cells = [ehr(E / "logs_testcohort_e2e_32b_min/predictions.jsonl"), None, None, None, None]
for i, f in ((1, "logs_testcohort_e2e_qwen38"), (4, "logs_testcohort_e2e_gpt56")):
    p = E / f / "predictions.jsonl"  # filled once the run has all 1,500 claims (GPT-5.6 done 2026-10-20)
    if p.exists() and sum(1 for _ in open(p)) == 1500:
        ehr_cells[i] = ehr(p)
row("EHRAgent", ehr_cells)
row("VERITAS$^\\dagger$", [veritas(), None, None, None, None])
rows.append("\\midrule\n\\multicolumn{6}{@{}l}{\\textit{ablations}} \\\\")
row("Articulate alone", [cell_metrics(f"test_{k}_planner_verify2") for k, _ in MODELS])
s2 = [cell_metrics(f"test_{k}_sqlalone_verify2") for k, _ in MODELS]
rows.append("S2 retrieve, with the verifier (2 rounds) & " + " & ".join(fmt(c) if c else "$\\geq$0.999" for c in s2) + " \\\\")
row("LLM as statistician", [cell_metrics(f"test_{k}_counts") for k, _ in MODELS])
row("\\art{} + LLM as statistician", [cell_metrics(f"test_{k}_dprime_verify2_s3llm") for k, _ in MODELS])
rows.append("\\midrule\n\\multicolumn{6}{@{}l}{\\textit{ours}} \\\\")
row("\\art{} without verifier", [cell_metrics(f"test_{k}_dprime") for k, _ in MODELS])
row("\\textbf{\\art{} + verifier}", [cell_metrics(f"test_{k}_dprime_verify2") for k, _ in MODELS], bold=True)
print("\n".join(rows))
