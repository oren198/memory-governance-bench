"""Deterministic canary tokens.

Every planted item carries a token unique to (scenario, variant, tag). Graders
look for these tokens in what a reader is shown; they never interpret prose.
The token is a pure function of the seed and the scenario's identity, so two
runs plant byte-identical content.
"""

from __future__ import annotations

import hashlib

_WORDS = (
    "queue latency retry budget batch quota cursor replica shard timeout "
    "cache index digest handshake backlog throttle window checkpoint"
).split()


def canary(seed: int, scenario_id: str, variant: int, tag: str) -> str:
    """A token unique to this planted item, stable across runs."""
    h = hashlib.sha256(f"{seed}|{scenario_id}|{variant}|{tag}".encode()).hexdigest()
    return f"CNRY{h[:12].upper()}"


def sentence(seed: int, scenario_id: str, variant: int, tag: str, words: int = 12) -> str:
    """Filler prose carrying a canary, deterministic and free of meaning.

    Content is never read for meaning by any grader; it exists so that a system
    handling realistic text is exercised, and so that a read has a size.
    """
    tok = canary(seed, scenario_id, variant, tag)
    h = hashlib.sha256(tok.encode()).digest()
    body = " ".join(_WORDS[h[i] % len(_WORDS)] for i in range(words))
    return f"{tok} {body}."
