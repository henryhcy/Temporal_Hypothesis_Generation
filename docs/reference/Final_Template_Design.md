# Temporal Hypothesis Benchmark — Final Template Design

A benchmark for **temporal hypothesis verification** over clinical narratives (VAERS reports in the MedTempo corpus). Each item gives a framework a set of raw narratives plus one natural-language hypothesis about a temporal pattern; the framework must locate the evidence and return **supported / refuted / insufficient**. Gold labels are computed deterministically from expert timelines.

The design is **24 template groups**: **17 hypothesis-test groups** (scored below over the whole corpus) and **7 report-level groups** (single-narrative facts, deterministic — no test).

---

## Design principles

1. **Every cohort-level claim is a hypothesis test with a principled null** — a chance baseline (a coin-flip 0.5, a uniform distribution, or "this ordering beats its nearest rival"), or a comparison to another group. No claim is graded by simply matching an observed number.
2. **Significance *is* the verdict (a three-decision test).** For a claim that names a direction: significant in that direction → *supported*; significant in the *opposite* direction → *refuted*; not significant either way → *insufficient*. Refuted always means significant counter-evidence, never merely "unproven."
3. **Directional tests are one-sided at α = 0.05 per side**, in the observed direction — chosen to maximize usable cases (under a true null the chance of declaring *some* direction is ≈ 2α).
4. **No absolute-percentage claims.** "In ~40% of reports…" is a fact-check with no null, so those groups were retired.
5. **Two-cohort comparisons are directional only** ("higher after v1 than v2"). "Do they differ / are they the same" was removed: a significance test can reject the no-difference null but never confirm it, so those shapes have no clean supported/refuted.
6. **Report-level claims are exact facts** about one narrative — deterministic, no statistics.

---

## The 24 templates

Scope: **report** = one narrative · **vaccine** = one cohort · **multi** = two-cohort comparison.

### precedes

| ID | Scope | Type | Hypothesis | Null / reference | Test |
|---|---|---|---|---|---|
| P-R1 | report | BOOL | A occurred before B in this report | - | exact |
| P-R2 | report | CHOICE | which came first in this report, A or B | - | exact |
| P-V1 | vaccine | BOOL | A typically precedes B | P = 0.5 | binomial (1-sided) |
| P-V2 *(new)* | vaccine | BOOL | A precedes B more often than C precedes B | P(A<B) = P(C<B) | Fisher 2x2 (1-sided) |
| P-V3 | vaccine | CHOICE | which usually comes first, A or B | P = 0.5 | binomial (1-sided) |
| P-V4 *(new)* | vaccine | BOOL | A precedes B more often than C precedes D | P(A<B) = P(C<D) | Fisher 2x2 (1-sided) |
| P-M2 | multi | CHOICE | A precedes B more often after v1 than v2 | p1 = p2 | Fisher 2x2 (1-sided) |

### co-occurs

| ID | Scope | Type | Hypothesis | Null / reference | Test |
|---|---|---|---|---|---|
| C-R1 | report | BOOL | A and B co-occur in this report | - | exact |
| C-V1 | vaccine | BOOL | A and B typically co-occur | P = 0.5 | binomial (1-sided) |
| C-V2 *(new)* | vaccine | BOOL | A and B occur together more than if independent | independence | Fisher 2x2 (1-sided) |
| C-V3 | vaccine | BOOL | co-occurrence is the dominant relation for A, B | P = 0.5 | binomial (1-sided) |
| C-M2 | multi | CHOICE | A and B co-occur more often after v1 than v2 | p1 = p2 | Fisher 2x2 (1-sided) |

### sequence

| ID | Scope | Type | Hypothesis | Null / reference | Test |
|---|---|---|---|---|---|
| S-R1 | report | BOOL | order is A -> B -> C in this report | - | exact |
| S-V1 | vaccine | BOOL | A -> B -> C is the most common ordering | modal = runner-up | binomial modal-vs-runner-up (1-sided) |
| S-V3 | vaccine | CHOICE | the most common ordering of A, B, C | uniform (6 orderings) | multinomial GOF |
| S-V4 | vaccine | BOOL | the ordering of A, B, C is consistent across reports | uniform (6 orderings) | multinomial GOF |
| S-M2 | multi | CHOICE | A -> B -> C more common after v1 than v2 | p1 = p2 | Fisher 2x2 (1-sided) |

### first/last

| ID | Scope | Type | Hypothesis | Null / reference | Test |
|---|---|---|---|---|---|
| F-R1 | report | CHOICE | which occurs first in this report | - | exact |
| F-R2 | report | CHOICE | which occurs last in this report | - | exact |
| F-R3 | report | BOOL | A is the first of A, B, C in this report | - | exact |
| F-V1 | vaccine | CHOICE | which typically occurs first | uniform (3 candidates) | multinomial GOF |
| F-V2 | vaccine | CHOICE | which typically occurs last | uniform (3 candidates) | multinomial GOF |
| F-V3 | vaccine | BOOL | A is the most common first event | modal = runner-up | binomial modal-vs-runner-up (1-sided) |
| F-M3 | multi | CHOICE | A is first more often after v1 than v2 | p1 = p2 | Fisher 2x2 (1-sided) |

---

## Whole-corpus results

For every **case** — one distinct event-combination asked about in a cohort — we run its three-decision test over all 3,166 reports. A case is **decisive** when the test is significant: it can then be posed as a *supported* claim (oriented with the effect) or a *refuted* one (oriented against it). An **indecisive** case (not significant either way) can only be *insufficient*. So the number that matters per template is **S = decisive cases** — the shared resource behind both supported and refuted. **Median n** = median reports behind one case.

**Headline:** the cohort-level groups supply **2,627 decisive cases**. Sampled to an equal ⅓ / ⅓ / ⅓ verdict mix (one claim per decisive case), that is a balanced benchmark of **≈ 3,940 items** — about 1,314 supported + 1,314 refuted from the decisive cases, plus an equal insufficient slice. Supply is dominated by the pairwise/co-occurs groups; sequence and multi groups are thin (gradient below). New-group counts *(new)* are candidate-inventory ceilings.

| ID | Scope | Test | Decisive cases (S) | Balanced items (≈1.5·S) | Median n |
|---|---|---|--:|--:|--:|
| P-V1 | vaccine | binomial (1-sided) | 218 | 327 | 15 |
| P-V2 *(new)* | vaccine | Fisher 2x2 (1-sided) | 372 | 558 | 29 |
| P-V3 | vaccine | binomial (1-sided) | 218 | 327 | 15 |
| P-V4 *(new)* | vaccine | Fisher 2x2 (1-sided) | 415 | 622 | 28 |
| P-M2 | multi | Fisher 2x2 (1-sided) | 30 | 45 | 16 |
| C-V1 | vaccine | binomial (1-sided) | 378 | 567 | 16 |
| C-V2 *(new)* | vaccine | Fisher 2x2 (1-sided) | 144 | 216 | 1019 |
| C-V3 | vaccine | binomial (1-sided) | 378 | 567 | 16 |
| C-M2 | multi | Fisher 2x2 (1-sided) | 43 | 64 | 18 |
| S-V1 | vaccine | binomial modal-vs-runner-up (1-sided) | 4 | 6 | 6 |
| S-V3 | vaccine | multinomial GOF | 14 | 21 | 6 |
| S-V4 | vaccine | multinomial GOF | 14 | 21 | 6 |
| S-M2 | multi | Fisher 2x2 (1-sided) | 0 | 0 | 6 |
| F-V1 | vaccine | multinomial GOF | 130 | 195 | 14 |
| F-V2 | vaccine | multinomial GOF | 176 | 264 | 14 |
| F-V3 | vaccine | binomial modal-vs-runner-up (1-sided) | 74 | 111 | 14 |
| F-M3 | multi | Fisher 2x2 (1-sided) | 19 | 28 | 14 |

### Decisive-case supply by family (live groups)

| Family | Cases | Decisive (S) | Decisive rate |
|---|--:|--:|--:|
| precedes | 1,472 | 466 | 32% |
| co-occurs | 2,497 | 799 | 32% |
| sequence | 915 | 32 | 3% |
| first/last | 2,654 | 399 | 15% |

> **Reading the gradient.** Pairwise/co-occurs questions rest on ~30 reports each, so most cases are decisive; sequence and two-cohort questions slice the corpus down to ~6–8 reports, so most cases are indecisive. This is a property of the corpus, not the tests — it is exactly what makes the verdicts non-trivial.

### Benchmark composition (target)

- **Verdict mix:** ~1/3 supported, 1/3 refuted, 1/3 insufficient per group — equal thirds, so every trivial policy (always-supported "yes-man," always-insufficient) scores only ~33%.
- **Sourcing:** supported and refuted are drawn from the decisive cases, one claim per case and from *different* event combinations (never the A→B / B→A mirror of a single case). Budget per group ≈ 1.5·S; groups with tiny S (sequence) are taken in full and flagged as starved.
- **Insufficient spans three kinds:** *underpowered* (co-occur enough, no significant effect), *sparse* (co-occur but below the sample-size floor), and *not-locatable* (events absent or never co-occurring, n = 0). The last is added deliberately — it tests that the framework answers "insufficient" instead of inventing a relationship.
- **Grading:** per-class precision/recall and macro-F1, not bare accuracy.

---

## What changed in the redesign

The roster went from 30 → **24** groups. Retired:

| Groups | Shape | Why removed |
|---|---|---|
| P-V2, C-V2, S-V2 (old) | PROP | absolute-rate fact-check -- no principled null (P-V2/C-V2 IDs reused below) |
| P-M1, C-M1, S-M1 | rate differ | "differ" has no clean refuted (can't accept H0) |
| S-M3, F-M1 | same | "same" is the null -- can never be supported |
| F-M2 | differ-first | same defect as the other differ groups |

Added three single-cohort groups with principled nulls: **P-V2** (does A precede B more than C does?), **P-V4** (does one pair's ordering beat another's?), **C-V2** (are A and B associated beyond chance?). The freed **P-V2 / C-V2** IDs are reassigned to these new groups (the retired PROP claims no longer exist); **P-V4** is a new ID. Reworded **S-V1 / F-V3** from vague "typically" to a testable "most common" (verified against the nearest rival).

> New-group counts (P-V2, P-V4, C-V2) come from the candidate inventory (full corpus, most-frequent-events enumeration) and are ceilings pending pipeline integration; their **decidable rates** are the comparable figure. C-V2's association test spans the entire cohort (~1,000 reports), hence its large median n.

