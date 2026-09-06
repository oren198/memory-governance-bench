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

# An item names something the group it is written in could plausibly hold an
# observation about. A system may weigh relevance when deciding what to admit,
# and a note about the search index written into a billing group is a fair
# thing to hesitate over — so the benchmark does not plant one. The nouns are
# the group's own; nothing else about the measure changes.
_SUBJECTS_BY_ROLE = {
    "company": ("the deploy pipeline", "the release train", "the access review job", "the status page updater", "the audit log shipper", "the config service", "the build cache", "the artifact store"),
    "sales": ("the lead import", "the CRM sync", "the quote generator", "the trial provisioning job", "the demo reset job", "the renewal reminder", "the pricing service", "the territory assigner"),
    "support": ("the ticket queue", "the macro sync", "the escalation router", "the chat widget", "the survey sender", "the backlog sweeper", "the transcript store", "the handoff report builder"),
    "tier2": ("the diagnostics runner", "the replay tool", "the escalation backlog", "the log search", "the repro harness", "the trace collector", "the defect sync", "the crash grouper"),
    "billing": ("the invoice run", "the payments gateway", "the dunning job", "the refund queue", "the tax lookup", "the card retry loop", "the statement export", "the proration check"),
    "collections": ("the reminder scheduler", "the write-off review job", "the debt export", "the payment-plan builder", "the arrears report", "the chase list generator", "the settlement processor", "the hardship queue"),
    "finance": ("the ledger export", "the month-end close job", "the revenue report builder", "the tax rules sync", "the accrual job", "the audit trail export", "the budget rollup", "the reconciliation run"),
}

# Used when a scenario builds its own fleet rather than the standard one.
_SUBJECTS = (
    "the checkout service", "the export job", "the retry queue",
    "the session cache", "the notification worker", "the search index",
    "the scheduler", "the archive job",
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

# A note is a standing belief about how something behaves, not a reading off
# a dial. A memory system may reasonably decline to hold "the queue was 141
# long on Tuesday" — it is a measurement, true when taken and worth nothing
# afterwards — and a benchmark that planted only measurements would fail
# systems for declining to remember what nobody should remember. Each frame
# below says something that stays true, and carries a number so that no two
# planted items are the same claim. The twelve are about twelve different
# properties — retries, timeout, concurrency, ownership, backlog, scaling,
# retention, log noise, manual work, scheduling, cost, breakage — and worded
# so that no two can be read as claims about the same one. Two frames a
# reader could take as the same property, filled with different numbers for
# one subject, are a contradiction the benchmark planted by accident.
_OBSERVED = (
    "{s} starts duplicating work if it is retried more than {v} times",
    "{s} needs its timeout kept at {v} seconds, since below that it fails in the {w} window",
    "{s} cannot run twice at once, and the second run stalls for about {v} minutes",
    "{s} still depends on a config file nobody owns, last changed on day {d}",
    "{s} carries a backlog of roughly {v} items that clears only after the {w} window",
    "{s} falls behind whenever it is scaled below {v} workers",
    "{s} keeps only {v} days of history, which is too little to investigate a late report",
    "{s} logs a warning roughly {v} times a day that can safely be ignored",
    "{s} has needed manual intervention on day {d} of the month since the last migration",
    "{s} must not start until the {w} window has closed, about {v} minutes in",
    "{s} accounts for about {v} percent of the team's compute spend",
    "{s} stops working whenever the {w} window shifts, as it did on day {d}",
)

# A plausible magnitude per frame: "retried more than 347 times" is not a
# belief anyone would hold, and a number out of range makes the sentence
# false in a way a reader would notice.
_RANGES = (
    (2, 6), (5, 120), (3, 45), (1, 28), (20, 400), (2, 12),
    (7, 90), (2, 60), (1, 28), (5, 90), (2, 40), (1, 28),
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
    """A token unique to this planted item, stable across runs.

    Graders look for it in what a reader is shown. It is written into content
    as a trailing reference, never as the sentence's subject."""
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
    role: str | None = None,
) -> str:
    """A plausible statement carrying a canary, deterministic across runs.

    `words` is a soft floor: the text grows by whole clauses until it is long
    enough, because truncating mid-clause would put back the nonsense this
    generator exists to avoid — but it never repeats a clause to get there,
    so an item may fall short of the floor. `ordinal` distinguishes this item from the
    others its scenario plants, so no two are the same claim.
    """
    tok = canary(seed, scenario_id, variant, tag)
    h = hashlib.sha256(tok.encode()).digest()
    # Rotation is per scenario, not per item: an offset that varied with the
    # item would collide, which is the thing `ordinal` exists to prevent.
    rot = hashlib.sha256(f"{seed}|{scenario_id}|{variant}".encode()).digest()[0]
    subjects = _SUBJECTS_BY_ROLE.get(role or "", _SUBJECTS)
    if kind == "rule":
        subject = subjects[(rot + ordinal) % len(subjects)]
        # Drawn without replacement: the first len(_RULES) rules a scenario
        # plants are all different instructions, not one instruction restated.
        body = _RULES[(h[1] + ordinal) % len(_RULES)].format(s=subject)
        tails = _RULE_TAILS
    else:
        # One index over (frame x subject), so the pair is unique for the
        # first len(_OBSERVED) * len(_SUBJECTS) items a scenario plants — more
        # than the largest flood — and no frame is reused with a fresh noun.
        combo = (rot + ordinal) % (len(_OBSERVED) * len(subjects))
        index = combo % len(_OBSERVED)
        frame = _OBSERVED[index]
        lo, hi = _RANGES[index]
        subject = subjects[combo // len(_OBSERVED)]
        body = frame.format(
            s=subject,
            v=lo + (ordinal * 7 + h[2]) % (hi - lo + 1),
            w=_WINDOWS[(h[3] + ordinal) % len(_WINDOWS)],
            d=1 + (h[4] + ordinal) % 28,
        )
        tails = _NOTE_TAILS
    # The token trails as a reference rather than leading as a subject. A bare
    # identifier at the head of a sentence reads as something the item is
    # about, and a system reading its input will fairly ask what it is; as a
    # trailing reference it is what it actually is — a label on the claim.
    parts = [f"{body} (ref {tok})."]
    # Distinct trailers only, and the floor yields when they run out: the same
    # sentence twice reads as noise, and a system that declines noise is right
    # to. A short item is honest; a padded one is not.
    for k in range(len(tails)):
        if len(" ".join(parts).split()) >= words:
            break
        parts.append(f"{tails[(rot + ordinal + k) % len(tails)]}.")
    return " ".join(parts)
