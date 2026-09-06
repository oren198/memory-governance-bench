"""Deterministic canary tokens and the sentences that carry them.

Every planted item carries a token unique to (scenario, variant, tag). Graders
look for these tokens in what a reader is shown; they never interpret prose.
The token is a pure function of the seed and the scenario's identity, so two
runs plant byte-identical content.

The prose around the token is generated, but it is not filler. A system may
decide what it is willing to admit into memory, and a system that reads its
input will decline text that means nothing. If the benchmark plants word
salad, such a system fails every measure downstream of a write, and the
failure says nothing about how it governs memory — it says the benchmark
wrote nonsense. So the sentences here are ordinary operational statements: a
rule reads as an instruction, a note reads as an observation, and both stay
deterministic. What the benchmark still refuses to do is depend on their
meaning. Legitimacy is known by construction, never inferred from the words.

Two planted items in one scenario must also be different *claims*, not one
claim with a noun swapped. A system that treats a near-identical restatement
as a duplicate rather than as new evidence is behaving well, so notes carry
a measurement whose value is unique to the item, and rules are drawn without
replacement. `ordinal` is the item's position among the distinct items its
scenario has planted, which is what makes both possible.
"""

from __future__ import annotations

import hashlib

_SUBJECTS = (
    "the checkout service", "the billing pipeline", "the retry queue",
    "the search index", "the export job", "the session cache",
    "the payments gateway", "the notification worker",
)

_RULES = (
    "{s} must not be deployed without a rollback plan written first",
    "every change to {s} requires a second reviewer before it is merged",
    "{s} must be drained before any migration begins",
    "no credential for {s} may be shared outside the owning team",
    "{s} must fail closed when its upstream is unavailable",
    "any incident touching {s} must be written up within one working day",
    "{s} may not be scaled down during a release window",
    "access to {s} in production is granted for a single named change only",
)

_OBSERVED = (
    "{s} handled {v} requests in the hour after the {w} window opened",
    "{s} spent {v} milliseconds in its slowest call on day {d} of the month",
    "{s} retried {v} times before it succeeded during the {w} window",
    "{s} left {v} items unprocessed when the {w} window closed",
    "{s} logged {v} warnings on day {d}, none of which were acted on",
    "{s} ran {v} seconds behind its schedule for most of day {d}",
    "{s} dropped {v} connections while the {w} window was open",
    "{s} was restarted {v} times on day {d} without a clear trigger",
    "{s} held {v} rows in its buffer at the end of the {w} window",
    "{s} answered {v} health checks late on day {d}",
    "{s} used {v} percent more memory during the {w} window than the week before",
    "{s} queued {v} jobs that were still waiting when day {d} ended",
)

_WINDOWS = ("morning", "overnight", "end-of-month", "release", "peak-traffic")

_RULE_TAILS = (
    "This applies in every environment, including staging",
    "It is checked as part of the deploy pipeline",
    "The same holds during incident response",
    "This holds until it is revisited",
    "It covers both scheduled and manual runs",
    "The scope is limited to production traffic",
)

_NOTE_TAILS = (
    "The pattern is clearest in the afternoon",
    "It affects a small share of requests",
    "The effect is limited to the batch path",
    "It shows up only under load",
    "The behaviour is the same in staging",
    "Nothing has changed since then",
)


def canary(seed: int, scenario_id: str, variant: int, tag: str) -> str:
    """A token unique to this planted item, stable across runs."""
    h = hashlib.sha256(f"{seed}|{scenario_id}|{variant}|{tag}".encode()).hexdigest()
    return f"CNRY{h[:12].upper()}"


def sentence(
    seed: int,
    scenario_id: str,
    variant: int,
    tag: str,
    words: int = 12,
    kind: str = "note",
    ordinal: int = 0,
) -> str:
    """A plausible statement carrying a canary, deterministic across runs.

    `words` is a floor, not a cut: the text grows by whole clauses until it is
    long enough, because truncating mid-clause would put back the nonsense
    this generator exists to avoid. `ordinal` distinguishes this item from the
    others its scenario plants, so no two are the same claim.
    """
    tok = canary(seed, scenario_id, variant, tag)
    h = hashlib.sha256(tok.encode()).digest()
    # Rotation is per scenario, not per item: an offset that varied with the
    # item would collide, which is the thing `ordinal` exists to prevent.
    rot = hashlib.sha256(f"{seed}|{scenario_id}|{variant}".encode()).digest()[0]
    if kind == "rule":
        subject = _SUBJECTS[(h[0] + ordinal) % len(_SUBJECTS)]
        # Drawn without replacement: the first len(_RULES) rules a scenario
        # plants are all different instructions, not one instruction restated.
        body = _RULES[(h[1] + ordinal) % len(_RULES)].format(s=subject)
        tails = _RULE_TAILS
    else:
        # One index over (frame x subject), so the pair is unique for the
        # first len(_OBSERVED) * len(_SUBJECTS) items a scenario plants — more
        # than the largest flood — and no frame is reused with a fresh noun.
        combo = (rot + ordinal) % (len(_OBSERVED) * len(_SUBJECTS))
        frame = _OBSERVED[combo % len(_OBSERVED)]
        subject = _SUBJECTS[combo // len(_OBSERVED)]
        body = frame.format(
            s=subject,
            v=101 + ordinal * 7 + h[2],       # unique to this item
            w=_WINDOWS[(h[3] + ordinal) % len(_WINDOWS)],
            d=1 + (h[4] + ordinal) % 28,
        )
        tails = _NOTE_TAILS
    parts = [f"{tok}: {body}."]
    n = 5
    while len(" ".join(parts).split()) < words:
        parts.append(f"{tails[(h[n % len(h)] + ordinal) % len(tails)]}.")
        n += 1
    return " ".join(parts)
