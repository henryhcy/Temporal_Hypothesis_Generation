"""Pseudonymous report ids (decisions.md 2026-10-08, the v1.2 review, item 4).

Every report id a model can see -- in the claim texts (``MT-0482913``), in the
release's ``cohort.report_id`` / ``evidence_ids`` and in the eval DB's
``report_id`` column -- is a KEYED PERMUTATION of the VAERS id, never the VAERS
id itself. VAERS is public, so a model that has seen it in pretraining could
otherwise look a report up by its id; the pseudonym removes that key while
keeping every id stable across regenerations under the same secret.

The mapping is a bijection on ``[0, 10**7)`` (VAERS ids are 6-7 digits): a
6-round balanced Feistel network on 24 bits, keyed by HMAC-SHA256, with cycle
walking back into the decimal range. Being a permutation it is collision-free
without any stored table, so nothing but the key has to be kept -- and the key
never leaves ``data/private/`` (gitignored). Everything that GENERATES data
(``CorpusIndex.load``, ``build_eval_db``) must use the same key; the harness
itself never needs it, because it works in pseudonym space end to end.

The identity mapping exists for the unit tests only (``MEDTEMPO_PSEUDONYM_KEY=
identity``); the release scripts refuse it.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path

KEY_ENV = "MEDTEMPO_PSEUDONYM_KEY"
KEY_PATH = Path(__file__).resolve().parents[3] / "data" / "private" / "pseudonym.key"
IDENTITY = "identity"

DOMAIN = 10 ** 7          # VAERS ids are < 10^7; pseudonyms live in the same range
_HALF_BITS = 12           # 24-bit Feistel: 2^24 = 16.8M > 10^7
_MASK = (1 << _HALF_BITS) - 1
_ROUNDS = 6

# how a pseudonym is written in a claim text, and how the parsers read it back
REPORT_PREFIX = "MT-"
REPORT_RE = re.compile(r"MT-(\d{7})")


def report_ref(report_id: int) -> str:
    """The textual form of a (pseudonymous) report id: ``MT-0482913``."""
    return f"{REPORT_PREFIX}{int(report_id):07d}"


class Pseudonymizer:
    """``vaers_id -> report_id`` (and back) under one secret key."""

    def __init__(self, key: bytes | None):
        self._key = key

    # -- construction -------------------------------------------------------

    @property
    def is_identity(self) -> bool:
        return self._key is None

    @classmethod
    def from_hex(cls, text: str) -> "Pseudonymizer":
        text = text.strip()
        if text == IDENTITY:
            return cls(None)
        key = bytes.fromhex(text)
        if len(key) < 16:
            raise ValueError("pseudonym key must be at least 16 bytes")
        return cls(key)

    @classmethod
    def default(cls, path: Path = KEY_PATH) -> "Pseudonymizer":
        """The key from ``$MEDTEMPO_PSEUDONYM_KEY`` (hex, or ``identity`` for
        tests), else from ``data/private/pseudonym.key``; raises if neither exists."""
        env = os.environ.get(KEY_ENV)
        if env:
            return cls.from_hex(env)
        if path.exists():
            return cls.from_hex(path.read_text(encoding="utf-8"))
        raise FileNotFoundError(
            f"no pseudonym key: set {KEY_ENV} or create {path} "
            f"(python -c 'from temporal_hypo.core.pseudonym import Pseudonymizer; "
            f"Pseudonymizer.generate()'). The key is private and is NOT in git."
        )

    @classmethod
    def generate(cls, path: Path = KEY_PATH) -> Path:
        """Write a fresh 32-byte key (refuses to overwrite: losing the key
        changes every id in every release built with it)."""
        if path.exists():
            raise FileExistsError(f"{path} exists; refusing to overwrite a pseudonym key")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    # -- the permutation ----------------------------------------------------

    def _round(self, i: int, half: int) -> int:
        msg = f"{i}:{half}".encode()
        return int.from_bytes(hmac.new(self._key, msg, hashlib.sha256).digest()[:2], "big") & _MASK

    def _perm(self, x: int) -> int:
        left, right = x >> _HALF_BITS, x & _MASK
        for i in range(_ROUNDS):
            left, right = right, left ^ self._round(i, right)
        return (left << _HALF_BITS) | right

    def _perm_inv(self, y: int) -> int:
        left, right = y >> _HALF_BITS, y & _MASK
        for i in reversed(range(_ROUNDS)):
            left, right = right ^ self._round(i, left), left
        return (left << _HALF_BITS) | right

    def __call__(self, vaers_id: int) -> int:
        """The pseudonym of ``vaers_id`` (a bijection on ``[0, 10**7)``)."""
        x = int(vaers_id)
        if not 0 <= x < DOMAIN:
            raise ValueError(f"report id {x} outside [0, {DOMAIN})")
        if self._key is None:
            return x
        y = self._perm(x)
        while y >= DOMAIN:            # cycle walking: stay inside the decimal range
            y = self._perm(y)
        return y

    def inverse(self, report_id: int) -> int:
        """The VAERS id behind a pseudonym (private use: validation only)."""
        y = int(report_id)
        if not 0 <= y < DOMAIN:
            raise ValueError(f"report id {y} outside [0, {DOMAIN})")
        if self._key is None:
            return y
        x = self._perm_inv(y)
        while x >= DOMAIN:
            x = self._perm_inv(x)
        return x
