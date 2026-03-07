"""Utilities for teacher/admin identity generation and lookup."""

from __future__ import annotations

import re
import secrets
from pathlib import Path
from random import SystemRandom


_WORD_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_MIN_WORD_COUNT = 128
_DEFAULT_WORDS = (
    "anchor",
    "beacon",
    "canyon",
    "cedar",
    "comet",
    "copper",
    "delta",
    "ember",
    "falcon",
    "forest",
    "harbor",
    "juniper",
    "lantern",
    "maple",
    "meadow",
    "mint",
    "nebula",
    "orbit",
    "otter",
    "prairie",
    "quartz",
    "ridge",
    "river",
    "spruce",
    "summit",
    "timber",
    "valley",
    "willow",
)


def _word_list_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "random_words.txt"


def load_teacher_id_words() -> list[str]:
    """Load and sanitize words used for teacher public IDs."""
    words: list[str] = []
    path = _word_list_path()

    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            token = _WORD_TOKEN_RE.sub("", raw.strip().lower())
            if len(token) >= 3:
                words.append(token)

    # Dedupe while preserving order
    deduped = list(dict.fromkeys(words))
    if len(deduped) >= _MIN_WORD_COUNT:
        return deduped

    # Fallback guarantees generation if the file is missing or malformed.
    return list(_DEFAULT_WORDS)


def generate_teacher_public_id(words: list[str] | None = None) -> str:
    """Generate a random three-word public teacher ID like red_ocean_ridge."""
    word_pool = words or load_teacher_id_words()
    chooser = SystemRandom()
    return "_".join(chooser.choice(word_pool) for _ in range(3))


def generate_teacher_public_id_with_suffix(words: list[str] | None = None) -> str:
    """Generate an ID with a random suffix for collision fallback."""
    base = generate_teacher_public_id(words=words)
    return f"{base}_{secrets.token_hex(2)}"
