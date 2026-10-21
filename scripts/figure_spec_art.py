"""FigureSpec (figure-spec skill) versions of the three nested concept figures (user 2026-10-21):
the contract, the ART framework (abstract, no generation band) and the whole system with the STRATA
generation row. Writes the JSON specs, renders them with the skill's deterministic renderer to SVG,
and converts to PDF/PNG with cairosvg. No model calls.

    PYTHONPATH=src .venv313/bin/python scripts/figure_spec_art.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cairosvg

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "draft" / "Figures" / "figurespec"
SPECS = OUT / "specs"
RENDERER = Path.home() / ".claude" / "skills" / "figure-spec" / "scripts" / "figure_renderer.py"
SPECS.mkdir(parents=True, exist_ok=True)

# palette: coast blues for the model row, grey harness, warm-orange accent on the contract, sand gold
C = {
    "model_fill": "#DCE9F7", "model_stroke": "#5B8DB8",
    "input_fill": "#F1F3F6", "input_stroke": "#8A94A6",
    "codebook_fill": "#ECE6F6", "codebook_stroke": "#8E7CC3",
    "harness_fill": "#EDF0F3", "harness_stroke": "#8A94A6",
    "verify_fill": "#F7F8FA", "verify_stroke": "#9AA3B2",
    "contract_fill": "#FBE2C9", "contract_stroke": "#D9792F",
    "output_fill": "#DDF0E4", "output_stroke": "#5E9E6E",
    "gold_fill": "#FFF3D0", "gold_stroke": "#C9A227",
    "gen_fill": "#EAF0F7", "gen_stroke": "#7A8FB0",
    "muted_fill": "#F5F5F5", "muted_stroke": "#B0B0B0",
    "edge": "#4A5568", "accent": "#D9792F", "gold_edge": "#C9A227", "muted_edge": "#9A9A9A",
}
STYLE = {"font_family": "Helvetica, Arial, sans-serif", "font_size": 13, "bg_color": "#FFFFFF",
         "palette": [C["edge"], C["accent"], C["gold_edge"], C["muted_edge"]]}


def node(id_, label, x, y, w, h, role, sub=None, fs=None, shape="rounded"):
    n = {"id": id_, "label": label, "x": x, "y": y, "width": w, "height": h, "shape": shape,
         "fill": C[f"{role}_fill"], "stroke": C[f"{role}_stroke"], "text_color": "#1F2933"}
    if sub:
        n["sublabel"] = sub
    if fs:
        n["font_size"] = fs
    return n


def edge(a, b, label=None, style="solid", color=None, curve=False, thickness=2):
    e = {"from": a, "to": b, "style": style, "color": color or C["edge"], "thickness": thickness, "curve": curve}
    if label:
        e["label"] = label
    return e


# ---------------------------------------------------------------- level 2: the framework (abstract)
def framework_nodes(oy: float = 0, ox: float = 0):
    y_m, y_h, y_g = 110 + oy, 270 + oy, 430 + oy
    X = lambda v: v + ox
    nodes = [
        node("claim", "Claim", X(95), y_m - 26, 120, 40, "input"),
        node("db", "Timeline DB", X(95), y_m + 26, 120, 40, "input"),
        node("s1", "S1 Articulate", X(290), y_m, 160, 70, "model", "LLM → plan"),
        node("s2", "S2 Retrieve", X(640), y_m, 170, 70, "model", "LLM → SQL"),
        node("out", "Verdict", X(855), y_m, 130, 70, "output", "+ evidence sets, p"),
        node("codebook", "Codebook", X(95), y_h, 120, 70, "codebook", "stipulations"),
        node("v1", "Verify", X(230), y_h, 90, 70, "verify", "1 round", fs=12),
        node("contract", "Contract", X(440), y_h, 140, 70, "contract", "plan → exact rule"),
        node("v2", "Verify", X(570), y_h, 90, 70, "verify", "≤ 2 rounds", fs=12),
        node("sandbox", "Sandbox", X(680), y_h, 100, 70, "harness", "→ n, k, ids", fs=12),
        node("s3", "S3 Test", X(855), y_h, 130, 70, "harness", "exact, deterministic"),
        node("goldnote", "Stage gold", X(95), y_g, 120, 70, "gold", "any stage can be gold", fs=12),
        node("gplan", "Gold plan", X(290), y_g, 160, 60, "gold", "plan EM"),
        node("gev", "Gold evidence", X(655), y_g, 160, 60, "gold", "evidence F1, faithfulness"),
        node("gver", "Gold verdict", X(855), y_g, 130, 60, "gold", "accuracy, over/underclaim", fs=12),
    ]
    edges = [
        edge("claim", "s1"), edge("db", "s1"),
        edge("codebook", "s1"),
        edge("s1", "v1", curve=True), edge("v1", "s1", curve=True),
        edge("s1", "contract", "plan", curve=True),
        edge("contract", "s2", "contract", color=C["accent"], curve=True, thickness=3),
        edge("s2", "v2", curve=True), edge("v2", "s2", curve=True),
        edge("s2", "sandbox", "SQL"),
        edge("sandbox", "v2"),
        edge("sandbox", "s3", "n, k"),
        edge("s3", "out", "verdict"),
        edge("s1", "gplan", style="dotted", color=C["gold_edge"]),
        edge("sandbox", "gev", style="dotted", color=C["gold_edge"]),
        edge("s3", "gver", style="dotted", color=C["gold_edge"]),
    ]
    groups = [
        {"id": "g_model", "label": "model (LLM)", "node_ids": ["claim", "db", "s1", "s2", "out"], "fill": "#F3F7FB", "stroke": "#C9D8E8", "padding": 30},
        {"id": "g_harness", "label": "harness (deterministic)", "node_ids": ["codebook", "v1", "contract", "v2", "sandbox", "s3"], "fill": "#F6F7F8", "stroke": "#D3D8DF", "padding": 30},
        {"id": "g_gold", "label": "gold (released with the benchmark)", "node_ids": ["goldnote", "gplan", "gev", "gver"], "fill": "#FDFAEF", "stroke": "#E7DDB5", "padding": 30},
    ]
    return nodes, edges, groups


def spec_framework():
    nodes, edges, groups = framework_nodes()
    return {"title": "ART framework (abstract)", "canvas": {"width": 965, "height": 560}, "style": STYLE,
            "nodes": nodes, "edges": edges, "groups": groups}


# ---------------------------------------------------------------- level 1: the contract
def spec_contract():
    nodes = [
        node("plan", "Plan (output of S1)\nevents: Headache, Fatigue\ndenominator: ordered_pair\nnull: symmetric 0.5\ntest: binomial", 95, 120, 160, 130, "model", fs=11),
        node("lookup", "Harness lookup\nordered_pair → both present\nat distinct stages; same\nstage excluded; numerator:\nA earlier\nboth_present → …\nall_present_unique_first → …", 380, 115, 210, 160, "contract", fs=11),
        node("prompt", "Prompt to S2\nschema (column listing)\ncontract: count a report\niff …; one row per report", 665, 150, 160, 130, "model", fs=11),
        node("verifier", "Verifier (S2)\nchecks the rows against\nthe same rule", 665, 290, 160, 60, "verify", fs=11),
        node("prose", "Ablation: plan as prose\nplan JSON + whole codebook;\nS2 must find the rule itself", 95, 290, 160, 60, "muted", fs=11),
    ]
    edges = [
        edge("plan", "lookup", "named primitive"),
        edge("lookup", "prompt", "exact rule", color=C["accent"], thickness=3),
        edge("prose", "prompt", "plan JSON + whole codebook", style="dashed", color=C["muted_edge"]),
        edge("lookup", "verifier", "same rule", style="dotted", color=C["gold_edge"]),
    ]
    return {"title": "The contract", "canvas": {"width": 760, "height": 340}, "style": STYLE,
            "nodes": nodes, "edges": edges, "groups": []}


# ---------------------------------------------------------------- level 3: the whole
def spec_whole():
    ox = 230
    nodes, edges, groups = framework_nodes(ox=ox)
    gen = [("corpus", "Corpus", "annotated timelines", "input"),
           ("templates", "Templates", "26 groups, 7 families", "gen"),
           ("cores", "Cores", "mirror pairs, not-locatable", "gen"),
           ("sgold", "Stage gold", "plan, evidence, p, verdict", "gold"),
           ("screens", "Screens", "permutation nulls, oracle", "harness"),
           ("release", "Release", "claims, codebook, gold", "gen")]
    ys = [60, 140, 220, 300, 380, 460]
    for (id_, lab, sub, role), y in zip(gen, ys):
        nodes.append(node(id_, lab, 120, y, 150, 58, role, sub, fs=12))
    for (a, *_), (b, *_) in zip(gen[:-1], gen[1:]):
        edges.append(edge(a, b))
    edges.append(edge("release", "goldnote", "stage gold", style="dotted", color=C["gold_edge"]))
    edges.append(edge("release", "codebook", "claims, codebook", color=C["muted_edge"], curve=True))
    groups.insert(0, {"id": "g_gen", "label": "STRATA generation", "node_ids": [g[0] for g in gen], "fill": "#F2F5F9", "stroke": "#C9D3E0", "padding": 30})
    return {"title": "STRATA generation and the ART framework", "canvas": {"width": 1200, "height": 560}, "style": STYLE,
            "nodes": nodes, "edges": edges, "groups": groups}


def main() -> None:
    for name, spec in (("1_contract", spec_contract()), ("2_framework", spec_framework()), ("3_whole", spec_whole())):
        sp = SPECS / f"{name}.json"
        sp.write_text(json.dumps(spec, indent=1, ensure_ascii=False))
        v = subprocess.run([sys.executable, str(RENDERER), "validate", str(sp)], capture_output=True, text=True)
        print(name, "validate:", (v.stdout + v.stderr).strip().splitlines()[-1] if (v.stdout + v.stderr).strip() else "ok")
        svg = OUT / f"{name}.svg"
        r = subprocess.run([sys.executable, str(RENDERER), "render", str(sp), "--output", str(svg)], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout, r.stderr); continue
        cairosvg.svg2pdf(url=str(svg), write_to=str(OUT / f"{name}.pdf"))
        cairosvg.svg2png(url=str(svg), write_to=str(OUT / f"{name}.png"), output_width=spec["canvas"]["width"] * 2)
        print("wrote", svg, "+ pdf/png")


if __name__ == "__main__":
    main()
