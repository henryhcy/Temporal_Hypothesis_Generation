"""Tests for template loading and slot-filling."""

from __future__ import annotations

import pytest

from temporal_hypo.generation.templates import FORMATS, REGISTERS, load_groups, render


def test_load_all_groups():
    groups = load_groups()
    # 30 - the retired PROP groups (P-V2, C-V2, S-V2) - S-M2 (power-dead)
    #    - S-V4 (non-directional and unrescuable, removed 2026-08-11)
    #    - F-M3 (failed its permutation null, p_perm 0.188, removed 2026-08-11)
    #    - C-M2 (failed its null on four measurements, 0.202, removed 2026-08-11)
    #    - the six S=0 non-directional multi groups P-M1/C-M1/S-M1/S-M3/F-M1/F-M2
    #      (roster migration A removal half, 2026-08-14)
    #    + the addition half (same day, decisions.md batch 2): P-V2 and C-V2
    #      re-enter with NEW definitions (conditional antecedent; association
    #      vs independence -- not the retired PROP claims) plus P-V4 -> 20.
    #    + v1.2 (decisions.md 2026-10-07, issue 32): nine groups from the three
    #      new families -- position T-R1/T-V1, proximity Y-R1/Y-V1/Y-V2/Y-V3,
    #      threshold H-V1/H-V3/H-V5 -> 29.
    assert len(groups) == 29
    for gid in ("P-V1", "P-V2", "P-V4", "C-V2", "C-V3", "S-V3", "F-V3",
                "P-R1", "P-M2",
                "T-R1", "T-V1", "Y-R1", "Y-V1", "Y-V2", "Y-V3", "H-V1", "H-V3", "H-V5"):
        assert gid in groups
    for gid in ("S-V2", "S-M2", "S-V4", "F-M3", "C-M2",
                "P-M1", "C-M1", "S-M1", "S-M3", "F-M1", "F-M2"):
        assert gid not in groups


def test_every_variant_renders_with_full_slots():
    groups = load_groups()
    fillers = {"A": "Headache", "B": "Fever", "C": "Rash", "D": "Chills",
               "v": "Pfizer", "v1": "Pfizer", "v2": "Moderna",
               "r": "VAERS-1", "p": "70"}
    for g in groups.values():
        values = {s: fillers[s] for s in g.slots}
        for reg in REGISTERS:
            for fmt in FORMATS:
                text = render(g, reg, fmt, values)
                assert "{" not in text and "}" not in text


def test_missing_slot_raises():
    groups = load_groups()
    g = groups["P-V1"]  # needs A, B, v
    with pytest.raises(KeyError):
        render(g, "research", "claim", {"A": "Headache", "B": "Fever"})


def test_render_substitutes_values():
    groups = load_groups()
    g = groups["P-V1"]  # BOOL: A, B, v
    text = render(g, "media", "claim",
                  {"A": "Headache", "B": "Fever", "v": "Pfizer"})
    assert "Headache" in text and "Pfizer" in text


def test_argmax_claims_assert_the_slot_realize_actually_names():
    """Every argmax template must assert slot {A}, because `_realize_extreme_choice`
    and `_realize_modal_choice` put the NAMED event first.

    F-V2 and F-R2 asserted {C} instead, so all 59 F-V2 instances named an arbitrary
    non-answer event while `gold_answer` held the real winner -- e.g. "Headache is
    most commonly the last event among Nausea, Chills, Headache" with
    gold_answer='Nausea'. Caught on 2026-08-11 while building the sample instances.
    """
    import re
    groups = load_groups()
    argmax = {"F-V1", "F-V2", "F-V3", "F-R1", "F-R2", "F-R3", "S-V1", "S-V3"}
    for gid in sorted(argmax & set(groups)):
        for register, forms in groups[gid].variants.items():
            claim = forms["claim"]
            # the asserted event is the first event placeholder in the claim
            first = next((m.group(1) for m in re.finditer(r"\{([ABC])\}", claim)), None)
            assert first == "A", (
                f"{gid} [{register}] asserts slot {{{first}}}, but realize names "
                f"slot {{A}}: {claim!r}"
            )
