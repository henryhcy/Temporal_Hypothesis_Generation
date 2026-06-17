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

_TEMPLATE_FILES = ("pairwise.yaml", "sequence.yaml", "first_last.yaml")
REGISTERS = ("original", "research", "media", "clinical")
FORMATS = ("question", "claim")

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
            )
    return groups


def template_string(group: Group, register: str, fmt: str) -> str:
    """Return the raw template string for a register/format, validating keys."""
    if register not in REGISTERS:
        raise ValueError(f"unknown register: {register}")
    if fmt not in FORMATS:
        raise ValueError(f"unknown format: {fmt}")
    return group.variants[register][fmt]


def render(group: Group, register: str, fmt: str, values: Mapping[str, str]) -> str:
    """Fill a template's placeholders from ``values``.

    Every ``{slot}`` in the template must have a value, and no stray braces may
    remain afterwards -- both conditions raise, catching template drift.
    """
    template = template_string(group, register, fmt)
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
