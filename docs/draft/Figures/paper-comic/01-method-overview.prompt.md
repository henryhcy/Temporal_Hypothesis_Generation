# Page 1 — Method overview: ART over STRATA (paper-figure style, English, landscape 16:9)

Source: STRATA draft (docs/draft/body.tex, Method §4, Figure 1 caption). Prepared by the
paper-comic workflow (Step 4 content description + Step 5 structured prompt), 2026-10-21.
Nothing in this prompt is invented: every box, arrow and label is a module, hand-off or metric
named in the Method section.

## What this page must make clear

A claim about annotated clinical timelines is verified in three stages. The model only ever does
two things: articulate the claim as a plan (S1) and write the retrieval SQL (S2). Everything that
decides the answer is deterministic: the harness turns the plan into an exact rule (the contract)
before S2 sees it, a sandbox turns the SQL into counts and report-id sets, and S3 runs an exact
statistical test. Every stage has a released gold answer, so the figure's bottom row shows what
each stage is scored on.

## Layout (left to right, three rows)

Top row (model, light blue): 
- far left, two small input chips stacked: "Claim" (a sentence) and "Timeline DB" (annotated
  report timelines);
- "S1 Articulate (LLM)" with a tiny plan card inside: `events`, `denominator: ordered_pair`,
  `null p0 = 0.5`, `test: binomial`;
- a gap;
- "S2 Retrieve (LLM writes SQL)" with a tiny table motif: `report | in_den | in_num`;
- far right, "Verdict" chip: supported / refuted / insufficient, "+ evidence sets, p".

Middle row (harness, light grey; one box is the accent):
- under the inputs: "Codebook" (corpus stipulations as text) with an arrow up into S1;
- under S1: "Verify ⟳1" (plan vs codebook) with a short down-and-up arrow pair to S1;
- between S1 and S2, the ONLY accent-coloured box: "Contract: plan → exact rule". The plan
  arrow leaves S1 downward into this box and the contract arrow rises from it into S2 (a dip
  through the harness row);
- under S2: "Verify ⟳≤2" (rows vs rule) with a down-and-up arrow pair to S2, and next to it
  "Sandbox: SQL → n, k, ids" receiving the SQL arrow from S2;
- right: "S3 Test (exact test, deterministic)" receiving (n, k) from the sandbox and sending the
  verdict up to the Verdict chip.

Bottom row (gold, light yellow/sand): three boxes aligned under S1, S2, S3 with a thin dotted
line up to the stage they score: "Gold plan → plan EM"; "Gold evidence → evidence F1,
faithfulness"; "Gold verdict → accuracy, overclaim, underclaim". A left label reads "any stage
can be set to gold".

Reading order: inputs → S1 → (dip) contract → S2 → sandbox → S3 → verdict; then the gold row.

## Visible text (verbatim whitelist)

Claim; Timeline DB; Codebook; S1 Articulate; LLM → plan; Verify ⟳1; plan vs codebook;
Contract; plan → exact rule; S2 Retrieve; LLM → SQL; Verify ⟳≤2; rows vs rule; Sandbox;
→ n, k, ids; S3 Test; exact test, deterministic; Verdict; + evidence sets, p; Gold plan; plan EM;
Gold evidence; evidence F1, faithfulness; Gold verdict; accuracy, overclaim, underclaim;
any stage can be set to gold; arrow labels: plan, contract, SQL, n, k, verdict.
No other words. No numbers except the ones above.

## Structured prompt (paste-ready)

【Type】method overview / pipeline figure
【Style】paper-figure: white background, clean vector-like modules, rounded rectangles, thin
dark-grey strokes, sans-serif short labels, like a NeurIPS/ICML overview figure
【Language】English
【Topic】ART: articulate, retrieve, test — a three-stage pipeline for verifying temporal-statistical
claims over annotated clinical timelines, with the harness contract between S1 and S2
【Visual structure】
- landscape 16:9, three horizontal rows: model (top), harness (middle), gold (bottom)
- top row left→right: Claim + Timeline DB chips → S1 Articulate box (with a 4-line plan card) →
  [gap] → S2 Retrieve box (with a 2-row table motif) → Verdict chip
- middle row: Codebook (under the inputs, arrow up into S1); Verify ⟳1 under S1 with paired
  down/up arrows; the Contract box between S1 and S2, the plan arrow dips from S1 into it and
  the contract arrow rises from it into S2; Verify ⟳≤2 and Sandbox under S2 (SQL arrow down
  from S2 into Sandbox); S3 Test at the right of the middle row, (n, k) arrow from Sandbox,
  verdict arrow up into the Verdict chip
- bottom row: Gold plan, Gold evidence, Gold verdict aligned under S1, S2, S3, each joined to
  its stage by a thin dotted vertical line; small left label "any stage can be set to gold"
- main path arrows solid and slightly thicker than the loop arrows; dotted lines only for gold
【Text to render】exactly the whitelist above, nothing else
【Colour limits】
- background white; strokes and text dark grey (#2B2B2B)
- top row fill very light blue; middle row fill very light grey; bottom row fill very light sand
- ONE accent colour (warm orange) for the Contract box outline/fill and the "contract" arrow
- no gradients, no shadows, no 3-D
【Forbidden】
- no extra modules, icons, people, logos or decorative elements
- no numbers, formulas or results beyond the whitelist
- no title banner, no caption inside the image
- no copying of the paper's existing Figure 1 layout
- no empty regions larger than a quarter of the canvas; the diagram fills 75–85 % of the frame
