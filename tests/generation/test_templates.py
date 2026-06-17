"""Tests for template loading and slot-filling."""

from __future__ import annotations

import pytest

from temporal_hypo.generation.templates import FORMATS, REGISTERS, load_groups, render


def test_load_all_30_groups():
    groups = load_groups()
    assert len(groups) == 30
    for gid in ("P-V1", "C-V3", "S-V3", "F-M3", "P-R1"):
        assert gid in groups


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
    g = groups["P-V2"]  # PROP: A, B, v, p
    text = render(g, "media", "claim",
                  {"A": "Headache", "B": "Fever", "v": "Pfizer", "p": "62"})
    assert "62" in text and "Pfizer" in text
