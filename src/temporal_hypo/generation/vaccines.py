"""Canonical vaccine names and the v1 multi-vaccine pairs.

The DB stores the manufacturer name ``Janssen`` (mapped from the VAERS
``JANSSEN`` value in ``db/build.py``). Per the pilot decision, generated
hypothesis text uses the DB value verbatim -- ``Pfizer``, ``Moderna``,
``Janssen`` -- so cohort lookups via ``get_cohort(conn, name)`` and slot text
never drift. The plan docs informally write "Johnson"; we do not use that
string anywhere in code or output.
"""

from __future__ import annotations

VACCINES: tuple[str, str, str] = ("Pfizer", "Moderna", "Janssen")

# Two-vaccine pairs for v1 multi-vaccine groups (decisions.md: three pairs).
# Order within each pair is (v1, v2); CHOICE/direction verdicts read v1 as the
# cohort the claim asserts to be higher.
VACCINE_PAIRS: list[tuple[str, str]] = [
    ("Pfizer", "Moderna"),
    ("Pfizer", "Janssen"),
    ("Moderna", "Janssen"),
]
