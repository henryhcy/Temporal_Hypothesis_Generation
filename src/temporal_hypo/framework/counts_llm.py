"""Counts-only baseline: the verdict from the numbers, decided by a model.

WHAT. ``CountsVerdictTester`` is a stage-3 replacement. It takes the claim and
the GOLD retrieval, reduces them to the counts the exact test would see
(``n, k[, n2, k2]``), tells the model the test, the null, the tail, the floor
and alpha, and asks for the verdict. No text, no schema, no SQL -- roughly 300
prompt tokens per call.

WHY. Every other baseline confounds two things: finding the right reports and
knowing what to do with them. This one removes the first entirely. It answers a
question the analysis section needs and nothing else measures:

- if it scores HIGH, the model knows the three-decision rule, and every failure
  seen elsewhere is retrieval or extraction -- stage 3 is bookkeeping;
- if it scores LOW, the model cannot apply "one-sided exact at alpha = 0.05,
  floor 10" even when handed the numbers, and the deterministic stage 3 is
  itself a contribution -- no amount of better retrieval would rescue it.

The interesting failures are predictable and each is separately visible in the
scorer: calling a p just over alpha ``supported``; answering ``refuted`` for
"not significant" (the three-decision rule's whole point is that refuted needs
the OPPOSITE tail); and ignoring the min-n floor on the sparse rows.

SCOPE. The report tier has no counts -- it is a single exact observation -- so
those rows fall through to ``run_test`` unchanged and the cohort-tier number is
the result. Run with ``--groups`` set to the 13 cohort groups to keep the
headline clean.
"""

from __future__ import annotations

import json
from typing import Any

from temporal_hypo.framework.claim_schema import MODE_SPEC, StructuredClaim
from temporal_hypo.framework.extract.llm_client import Completion, Provider, parse_json_object
from temporal_hypo.framework.run_test import Prediction, run_test, to_viable_core

VERDICTS = ("supported", "refuted", "insufficient")

VERDICT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "p_claim": {"type": ["number", "null"]},
        "p_opposite": {"type": ["number", "null"]},
    },
    "required": ["verdict"],
    "additionalProperties": False,
}

_RULE = """THE DECISION RULE (three-decision, one-sided, alpha per side):
- supported    : p in the CLAIM's direction < alpha
- refuted      : p in the OPPOSITE direction < alpha
- insufficient : neither tail is below alpha
`refuted` requires positive counter-evidence in the opposite direction. "Not
significant" is `insufficient`, never `refuted`.
A denominator below the minimum-n floor is `insufficient` whatever the counts say."""


def counts_payload(claim: StructuredClaim, core: Any) -> dict:
    """Everything the exact test sees, and nothing else."""
    spec = MODE_SPEC[claim.mode]
    proc = claim.procedure
    out: dict[str, Any] = {
        "claim_is_about": spec.statistic,
        "test": proc.test,
        "null": {"kind": proc.null.kind, "p0": proc.null.p0},
        "claim_tail": proc.claim_tail,
        "alpha": proc.alpha,
        "min_n_floor": proc.min_n_floor,
        "arms": proc.arms,
        "negated": claim.negated,
        "counts": {"n": core.n, "k": core.k},
    }
    if proc.arms == 2:
        out["counts"].update({"n2": core.n2, "k2": core.k2})
    if getattr(core, "extra", None) and "counts" in (core.extra or {}):
        cells = core.extra["counts"]
        out["counts"]["cells"] = {str(k): v for k, v in cells.items()}
    return out


def counts_messages(claim: StructuredClaim, core: Any) -> list[dict]:
    system = "\n".join([
        "You decide the verdict of a statistical hypothesis from its counts. You are given the "
        "test, the null, the tail, the significance level and the minimum-n floor, plus the "
        "observed counts. Compute the exact test and apply the decision rule below. Answer with "
        'ONE JSON object {"verdict": "...", "p_claim": <number or null>, '
        '"p_opposite": <number or null>} and nothing else.',
        "",
        _RULE,
        "",
        "NOTES:",
        "- `k` of `n` is the count in the claim's asserted direction out of the conditioned "
        "denominator. For a two-arm test, arm 1 is the side the claim asserts is higher.",
        "- `p0` is the null proportion for a one-proportion test; for a two-arm test the null is "
        "that the two rates are equal.",
        "- If `negated` is true the claim asserts the NEGATION, so the claim tail is the other "
        "one.",
        "- Tests are EXACT (binomial / Fisher), not normal approximations.",
    ])
    user = ("HYPOTHESIS COUNTS (JSON):\n"
            + json.dumps(counts_payload(claim, core), ensure_ascii=False)
            + '\n\nReturn {"verdict": ...} now.')
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class CountsVerdictTester:
    """Stage 3 by model. Call it where ``run_test`` would go (``Pipeline.tester``)."""

    def __init__(self, client: Provider, model: str, *, temperature: float = 0.0,
                 max_tokens: int = 300) -> None:
        self.client = client
        self.model = model
        self.name = f"counts-llm:{model}"
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)
        self.last_error: str | None = None
        self.last_completions: list[Completion] = []

    def __call__(self, claim: StructuredClaim, retrieval: Any, *,
                 procedure_mode: str = "honouring") -> Prediction:
        self.last_error = None
        self.last_completions = []
        # No counts to reason from: keep the deterministic answer (module docstring).
        if claim.is_underdetermined or MODE_SPEC[claim.mode].is_report:
            return run_test(claim, retrieval, procedure_mode=procedure_mode)

        core = to_viable_core(claim, retrieval)
        reference = run_test(claim, retrieval, procedure_mode=procedure_mode)
        try:
            c = self.client.complete(counts_messages(claim, core),
                                     schema=VERDICT_JSON_SCHEMA, model=self.model,
                                     temperature=self.temperature, max_tokens=self.max_tokens)
            self.last_completions.append(c)
            raw = parse_json_object(c.text)
            verdict = str(raw.get("verdict", "")).strip().lower()
            if verdict not in VERDICTS:
                raise ValueError(f"verdict {verdict!r} is not one of {VERDICTS}")
            p_claim = raw.get("p_claim")
            p_opp = raw.get("p_opposite")
        except Exception as exc:  # noqa: BLE001 - one bad row must not kill the run
            self.last_error = f"{type(exc).__name__}: {exc}"
            # Scored as a miss, not skipped: `insufficient` is the model's own cop-out
            # class, so a parse failure lands in the class the metric already punishes.
            verdict, p_claim, p_opp = "insufficient", None, None

        # Counts, test name and CHOICE answer stay the reference ones: they are inputs
        # to this baseline, not predictions. Only the verdict (and the p's) are the model's.
        return Prediction(
            response=verdict, verdict=verdict, subtype=None,
            p_claim=(float(p_claim) if isinstance(p_claim, (int, float)) else None),
            p_opposite=(float(p_opp) if isinstance(p_opp, (int, float)) else None),
            test=reference.test, n=core.n, k=core.k, n2=core.n2, k2=core.k2,
            answer=reference.answer, gate_reason=None,
            procedure_errors=list(reference.procedure_errors), notes=list(reference.notes),
        )

    @property
    def last_tokens(self) -> dict | None:
        if not self.last_completions:
            return None
        p = [c.prompt_tokens for c in self.last_completions]
        k = [c.completion_tokens for c in self.last_completions]
        if any(x is None for x in p) or any(x is None for x in k):
            return None
        return {"prompt": sum(p), "completion": sum(k)}
