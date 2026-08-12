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
    assert len(groups) == 23
    for gid in ("P-V1", "C-V3", "S-V3", "F-V3", "P-R1"):
        assert gid in groups
    for gid in ("P-V2", "C-V2", "S-V2", "S-M2", "S-V4", "F-M3", "C-M2"):
        assert gid not in groups


def test_every_variant_renders_with_full_slots():
    groups = load_groups()
    fillers = {"A": "Headache", "B": "Fever", "C": "Rash",
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
