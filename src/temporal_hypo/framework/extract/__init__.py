"""Stage 1: hypothesis text -> ``StructuredClaim``.

Every extractor implements the same protocol so they are interchangeable::

    class Extractor(Protocol):
        name: str
        def extract(self, question_row: Mapping, *, blind_group: bool) -> StructuredClaim | None

``question_row`` carries ONLY ``instances.INPUT_FIELDS``. With ``blind_group=True``
the extractor must not read ``group_id`` (and must treat ``hypothesis_id`` as
opaque -- it embeds the group prefix). Returning ``None`` means "no parse"; a
claim with ``underdetermined`` roles means "parsed, but the input does not name
these events" (the harness answers ``underdetermined`` for those).

- ``rules.py`` -- reverse-template parser over the YAML templates (no model)
- ``llm.py``   -- prompted extraction through ``llm_client``
"""

from __future__ import annotations

from typing import Mapping, Protocol

from temporal_hypo.framework.claim_schema import StructuredClaim

# Fields an extractor may read under each input condition.
GIVEN_GROUP_FIELDS = ("group_id", "level", "answer_type", "register", "format",
                      "text", "options", "cohort")
BLIND_GROUP_FIELDS = ("level", "answer_type", "register", "format",
                      "text", "options", "cohort")


def visible_fields(question_row: Mapping, *, blind_group: bool) -> dict:
    """Project a question row onto the fields the condition allows."""
    keys = BLIND_GROUP_FIELDS if blind_group else GIVEN_GROUP_FIELDS
    return {k: question_row[k] for k in keys if k in question_row}


class Extractor(Protocol):
    name: str

    def extract(self, question_row: Mapping, *, blind_group: bool = False
                ) -> StructuredClaim | None: ...
