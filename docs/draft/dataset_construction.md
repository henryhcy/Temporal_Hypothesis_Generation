# Dataset Construction — draft for the Overleaf section

> DRAFT 2026-08-14, presented for approval before any Overleaf update.
> Every number is measured from `data/release/v1/dataset_statistics.json`
> or the committed screen results; nothing is estimated. All screens are
> COMPLETE: every shipping group cleared its 2000-round permutation null.

## 1. Source corpus

The benchmark is built on MedTempo: 3,166 VAERS adverse-event narratives
(1,019 Pfizer, 983 Moderna, 1,164 Janssen), each annotated with a *leveled
order* — a single totally-ordered chain of stages, where each stage holds the
MedDRA-coded events reported at that point of the course. Reports carry 2–14
stages (median 3) and 7.2 events on average over a vocabulary of 1,660
distinct terms. The annotation, not the narrative, is the benchmark's ground
truth and the framework's input: gold labels are computed mechanically from
the leveled orders, and the released instances reference report ids, never
text. When a term recurs, its first mention counts (locked rule); reports
whose earliest events tie at one stage are never asked order questions they
cannot answer (§4).

## 2. Hypothesis space

Twenty template groups span four temporal families — precedes, co-occurs,
strict sequence, first/last — at three scopes:

| | precedes | co-occurs / association | sequence | first/last |
|---|---|---|---|---|
| report | P-R1, P-R2 | C-R1 | S-R1 | F-R1, F-R2, F-R3 |
| one cohort | P-V1, P-V2, P-V3, P-V4 | C-V1, C-V2, C-V3 | S-V1, S-V3 | F-V1, F-V2, F-V3 |
| two cohorts | P-M2 | — | — | — |

Each group is realized in four registers (canonical Original plus Research,
Media, Clinical) and two formats (question, claim) by mechanical slot-filling
— no LLM rewriting — giving 8 text variants per instance. Answer types are
BOOL or CHOICE.

Three groups are two-proportion contrasts *within* one cohort, a shape the
grid previously lacked: P-V2 ("does {B} follow {A} more often than it follows
{C}?"), P-V4 ("does {A} precede {B} more often than {C} precedes {D}?"), and
C-V2 ("do {A} and {B} occur together more often than their separate rates
would predict?" — association vs independence). Both arms keep the full
cohort denominator, unlike the two-cohort tier, which splits the corpus.
C-V3 asks an argmax — "is co-occurrence the *dominant* relation for {A} and
{B}?" — over the three-cell relation distribution {before, after, co-occur}.

## 3. Gold labels

**Conditioning.** Each family fixes its denominator: precedes counts reports
where both events sit at distinct stages (co-existence is evidence neither
way); co-occurs counts all both-present reports; sequence requires all three
events at distinct stages; first/last requires every candidate present and
drops tie reports. The association group conditions on presence alone:
P(B | A present) against P(B | A absent).

**Tests, all exact.** One-sided exact binomial against 0.5 for majority
claims; modal-vs-runner-up (exact binomial on the named cell vs its best
competitor, null 0.5) for every argmax claim; Fisher's exact 2×2 for every
two-arm and two-cohort contrast. There is no chi-square anywhere and no
minimum expected cell count; the only gate is the per-family minimum
denominator (n ≥ 10; sequence n ≥ 5), applied to both arms where two exist.

**The three-decision rule.** A claim is *supported* only when its own tail is
significant (α = 0.05 one-sided), *refuted* only when the opposite tail is —
never "failed to prove" — and *insufficient* otherwise, sub-typed as
underpowered (testable but not decisive), sparse (0 < n < floor), or
not-locatable (n = 0). Report-level claims are single exact observations:
deterministic two-class verdicts, no test, no insufficient class.

**Oriented statistics.** Every released statistic — both one-sided p-values,
the 95% Wilson interval (Wilson–Newcombe on the difference for two-arm
shapes), and Cohen's h measured against the null the test actually uses —
describes the claim *as the instance asserts it*, not the core's canonical
orientation.

## 4. Instance realization

Every decisive core is posed **both ways**: once oriented with its effect
(supported) and once against it (refuted), forming a mirror pair that any
future split must keep together. Direction-asking groups re-orient by slot
swap (event order, the two arms, the two cohorts); symmetric claims (C-V1,
C-V2, C-V3) cannot, so they orient by **authored negation** — the negated
surface form is written in the template YAML, never derived — and samplers
prefer plain wording, negating only to fill the deficit. Report-level order
questions are posed only on reports that can answer them: the enumerator
picks the earliest fully-ordered pair or triple, so ties (62% of earliest
pairs) never generate unanswerable questions.

## 5. Balancing and the insufficient third

Each group ships **equal thirds** — supported, refuted, insufficient — capped
by its own decisive supply S, with the insufficient third spread across
sub-types by round-robin water-fill. Because enumeration only visits
combinations the corpus contains, the not-locatable sub-type is generated
deliberately: a seeded sampler mints claims from real cohort-vocabulary terms
whose joint count is zero (for the association group, a real corpus term
absent from that cohort), so the claim looks answerable and only querying the
store reveals an empty denominator. Report-level groups ship two balanced
classes by design.

## 6. Validity screens

No group ships on plausibility. Single-cohort order groups are screened
against a **level-shuffle** permutation null (term-to-stage assignment
shuffled within each report, preserving report size, stage-size multiset,
term frequencies and co-occurrence); the presence-based association group
against a degree-preserving **edge-swap** null; two-cohort shapes against a
**label-shuffle** null. A group ships only if its real decisive count beats
2,000 shuffled rounds at p ≤ 0.05.

| group | statistic | decisive / cores | null mean | p_perm |
|---|---|--:|--:|--:|
| C-V3 (argmax rework) | modal-vs-runner-up | 258 / 959 | 62.6 | **0.0005** |
| P-V2 | two-arm Fisher | 2,302 / 10,060 | 341.3 | **0.0005** |
| P-V4 | two-arm Fisher | 16,884 / 49,862 | 1,848.9 | **0.0005** |
| C-V2 | presence Fisher | 2,098 / 26,764 | 924.4 | **0.0005** |
| P-M2 (shipped 08-04) | two-cohort Fisher | 30 / 322 | 18.3 | 0.023–0.025 |

The screening history is itself a result: seven candidate two-cohort shapes
were tested against the label-permutation null and only P-M2 survived; the
retired majority statistic of C-V3 was replaced after the same method showed
its text and its test answered different questions; and the rank-test track
was retired as a verdict driver when the Mann-Whitney normal approximation
proved anti-conservative on tie-heavy ordinal data (~11% decisive under
shuffled labels at nominal 5%). Rank statistics survive in the release as
explicitly descriptive attributes.

## 7. Release format

Two files enforce the input/gold boundary mechanically.
`*_questions.jsonl` (one row per text variant) carries only the input
fields: hypothesis id, group, level, answer type, register, format, text,
options, cohort spec. `*_answers.jsonl` (one row per instance, listing its
eight question ids) carries the gold: verdict and sub-type, the oriented
counts (n, k, and both arms where two exist), both one-sided p-values, test
name, α, floor, CI, effect size, the **evidence report ids** (denominator,
numerator, excluded — the answer to the localization step, hence never
input), the descriptive positional block, negation and orientation
provenance, and two identifiers: `derived_from_core_id` (keeps mirror pairs
together) and the group-independent `fact_id` (statistic + cohort + events;
the split and every supply claim key on it, because answer-format twins ask
the same fact under two group ids). The writer raises if any non-input field
leaks into the questions file.

## 8. Validation

Gold labels are validated by six mechanical invariant families: evidence
arithmetic (id-set sizes reproduce n and k), set algebra, per-family
conditioning checked against the leveled orders, direction (every numerator
report satisfies the claim as asserted), verdict-vs-tails consistency with
the min-n gate, and independent recomputation of n and k through a separate
DB-backed code path (both arms, for the two-arm groups). The release run
passes all six; this validator has caught real bugs at every earlier stage
(a non-deterministic first-mention rule, wrong-cohort n₂/k₂, a wrong-event
claim wording), which is the argument for keeping it in CI.

## 9. Dataset statistics (v1 artifact)

| | |
|---|--:|
| records (instance × register × format) | 147,936 |
| instances | 18,492 |
| groups | 20 |
| distinct cores | 11,828 |
| distinct facts | 8,964 |
| supported / refuted / insufficient | 6,845 / 6,783 / 4,864 |
| insufficient sub-types | underpowered 1,729 / sparse 1,505 / not-locatable 1,630 |
| negated instances | 775 |
| mirror pairs | 6,664 |
| median conditioned n (IQR) | 26 (16–42) |
| median absolute effect size, decisive | 0.77 (Cohen's h) |

Per-group counts, distributions, and file hashes live in
`dataset_statistics.md` / `.json` beside the artifact.

## 10. Limitations, stated up front

Released text has no lexical variation (`synonym_used` echoes the raw MedDRA
term; a synonym table is future work). The sequence family survives at
cohort level with only S = 2 per group at release enumeration — taken in
full and flagged. P-V4's supply dominates the dataset (8,571 of 18,492
instances); consumers weighting by group should note it, and a per-group cap
is an open presentation choice. C-R1 ships 181/119 because its class is
fixed by the data (symmetric claim, no negation authored). Decisive labels
carry α-rate false positives by construction; the expected count per group
(exact, from the discrete test sizes) is reported with the artifact
[TO COMPUTE — issue 18, post-creation per decision]. Positional attributes
use the retired approximations and are descriptive only.
