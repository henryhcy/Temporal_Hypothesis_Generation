"""Load the template YAML groups and render slot-filled instance text.

The three YAML files under ``data/templates/`` are the single source of truth.
Each group declares an id, primitive, level, answer_type, slots, and four
register variants (original/research/media/clinical), each with a ``question``
and a ``claim`` string using ``{A} {B} {C} {v} {v1} {v2} {r} {p}`` placeholders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml

# Repo-root-relative default location of the canonical templates.
DEFAULT_TEMPLATES_DIR = (
    Path(__file__).resolve().parents[3] / "data" / "templates"
)

_TEMPLATE_FILES = ("pairwise.yaml", "sequence.yaml", "first_last.yaml",
                   "position.yaml", "proximity.yaml", "threshold.yaml")   # v1.2
REGISTERS = ("original", "research", "media", "clinical")
FORMATS = ("question", "claim")
# Negated surface forms, used when an instance asserts the claim's NEGATION.
# Authored in the YAML rather than derived, per the mechanical-generation rule:
# no programmatic rewriting of claim text.
NEGATED_FORMATS = {"question": "question_negated", "claim": "claim_negated"}

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class Group:
    """One template group (e.g. P-V1) with its four register variants."""

    id: str
    family: str
    primitive: str
    level: str
    answer_type: str
    slots: tuple[str, ...]
    # variants[register][format] -> template string
    variants: dict[str, dict[str, str]]
    # v1.2: the null the claim is tested against -- a number for a text-stated
    # bar ("at least two thirds" -> 0.667), "structural" for a data-derived
    # per-core null (position, adjacency), None for the symmetric 0.5 default.
    null_ref: float | str | None = None


def load_groups(templates_dir: Path | None = None) -> dict[str, Group]:
    """Load all template groups, keyed by group id."""
    base = templates_dir or DEFAULT_TEMPLATES_DIR
    groups: dict[str, Group] = {}
    for fname in _TEMPLATE_FILES:
        with open(base / fname, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        family = data["family"]
        for grp in data["groups"]:
            gid = grp["id"]
            if gid in groups:
                raise ValueError(f"duplicate group id: {gid}")
            groups[gid] = Group(
                id=gid,
                family=family,
                primitive=grp["primitive"],
                level=grp["level"],
                answer_type=grp["answer_type"],
                slots=tuple(grp["slots"]),
                variants=grp["variants"],
                null_ref=grp.get("null_ref"),
            )
    return groups


def template_string(group: Group, register: str, fmt: str, *,
                    negated: bool = False) -> str:
    """Return the raw template string for a register/format, validating keys."""
    if register not in REGISTERS:
        raise ValueError(f"unknown register: {register}")
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}")
    if not negated:
        return group.variants[register][fmt]
    key = NEGATED_FORMATS[fmt]
    try:
        return group.variants[register][key]
    except KeyError:
        raise ValueError(
            f"group {group.id} has no negated {fmt} for register {register!r}; "
            "negation must be authored in the template YAML"
        ) from None


def supports_negation(group: Group) -> bool:
    """True when every register carries both negated surface forms.

    Negation is the orientation operator for symmetric claims (decisions.md
    2026-08-11), so a group can only supply the class its data does not naturally
    fall on if its negated wording exists.
    """
    return all(k in group.variants[r]
               for r in REGISTERS for k in NEGATED_FORMATS.values())


def render(group: Group, register: str, fmt: str, values: Mapping[str, str],
           *, negated: bool = False) -> str:
    """Fill a template's placeholders from ``values``.

    Every ``{slot}`` in the template must have a value, and no stray braces may
    remain afterwards -- both conditions raise, catching template drift.
    """
    template = template_string(group, register, fmt, negated=negated)
    needed = set(_PLACEHOLDER_RE.findall(template))
    missing = needed - set(values)
    if missing:
        raise KeyError(
            f"group {group.id} [{register}/{fmt}] missing slot values: "
            f"{sorted(missing)}"
        )
    text = template.format_map({k: str(v) for k, v in values.items()})
    leftover = _PLACEHOLDER_RE.findall(text)
    if leftover:
        raise ValueError(
            f"group {group.id} [{register}/{fmt}] left unfilled slots: {leftover}"
        )
    return text
