# Fleet Memory Bench — Charter

A benchmark for **fleet memory**: shared memory for a fleet of agents that
have *different* goals, roles and authority — not one agent with many
instances. A fleet's memory is governed or it is worthless: without
governance, the first agent to write nonsense poisons every other agent's
work.

The benchmark scores one promise:

> Every agent in the fleet can contribute to shared memory, **and** no agent
> can corrupt what the fleet holds to be true.

Both halves. A memory that accepts everything is easy to poison; one that
accepts nothing never compounds. Every result is reported as a pair, never
as one number.

## Ground rules

1. **Black box.** The benchmark drives a system only through the API in
   `SPEC.md` (write, retract, share, unshare, read) and scores only what
   `read` returns. How the system decides — rules, models, humans, nothing —
   is invisible and irrelevant.
2. **Deterministic.** The benchmark contains no model calls. Every scenario
   is generated from a fixed seed, every grader is plain code over `read`
   output, and two runs against the same system state give the same score.
   Systems may use models internally; the benchmark never does.
3. **No mechanism words.** Measures are stated in terms of what a reader is
   shown. "Judge", "summary", "embedding", "prompt", "compaction" do not
   appear in a measure. If a measure cannot be stated without one, it tests
   an implementation, not the promise.
4. **No reference implementation defines correctness.** Correctness is
   derived from the promise in this file. A system failing a measure is a
   finding against the system.
5. **Only readers' evidence counts.** If a property is not visible to a
   reader, the benchmark does not score it.

## What a fleet memory must provide

Stated as expectations on behaviour, not on design.

**The fleet has structure.** Agents act from **scopes**. A scope is a group
that shares memory (a team, a role, a project). Scopes may **contain** other
scopes (an org contains departments contains teams), and a scope may
**reference** a peer scope it wants to hear from. Containment and reference
are different relations and the memory must treat them differently.

**Memory has two kinds of item.** An **observation** is something an agent
saw; it informs and does not bind. A **decision** is something an authority
settled; it binds every reader it covers. Readers must be able to tell which
is which.

**Authority flows down, never up.** A decision in a containing scope binds
every contained scope, at any depth, and must be shown to them in full — a
reader bound by a decision they cannot see cannot comply. A contained scope's
decisions never bind its container. An **operator** (a human or process
outside the agents) may decide for any scope directly, and such decisions
outrank the fleet's own.

**Working memory does not leak.** What a contained scope inherits is what
binds it — decisions — and nothing else. A container's observations are not
automatically its children's. A sibling's memory is not yours. An unrelated
scope's memory is not yours.

**Sharing is explicit, faithful, and reaches the readers it was offered to.**
A scope makes memory available to others by **sharing** it. What is shared
must be something the sharer actually holds. It reaches exactly the scopes
entitled to hear from the sharer (those that reference it, and those it
contains) — and travels no further on its own. When a reader passes it on,
the next reader is told it is second-hand and from whom.

**Retraction is an event, not an absence.** When a write or share is taken
back, every reader who was shown it is told it was withdrawn, and what was
withdrawn. Silent disappearance is a failure: a reader who cannot tell
"withdrawn" from "never there" cannot correct what they built on it.

**Attribution is a live claim.** An item shown as "according to X" asserts
that X holds it *now*. When X retracts, the attribution must go with it: the
item is either dropped, or re-stated on the reader's own evidence with the
attribution removed. Keeping "according to X" after X withdrew is a false
statement; keeping the content without the label but without own evidence is
laundering — the second claim is a copy of the first, and copies are not
corroboration.

**Contradictions are resolved, not stored.** A reader is never shown both
sides of a contradiction as if both held. A later, legitimate correction
replaces the earlier claim. An observation never displaces a decision.

**Growth is bounded and forgetting is honest.** The read surface for a scope
stays within a stated bound as writes accumulate. When the system drops or
condenses to stay bounded, binding decisions are never lost, and a reader can
discover that something was dropped. Obsolete items leave the read surface;
nothing retired reappears.

**Legitimate contributions land.** A true, relevant, non-conflicting
observation written by any agent is shown to the readers entitled to it. This
is the half that stops every rule above from being satisfied by refusing to
remember anything.

## The failure modes

Every measure family is named for the failure it catches.

| Family | Failure it catches | Reader-visible symptom |
|---|---|---|
| **C — Containment** | Relevance collapse | Reader is shown an item from a scope they are not entitled to |
| **A — Authority** | Authority confusion | Decisions and observations blur; a binding decision is missing or mislabelled; origin label is false |
| **T — Truth maintenance** | Contamination | A planted false, malicious, or injected item is shown; both sides of a contradiction are shown; a correction did not replace its target |
| **E — Echo** | Echo chamber | A restatement is counted as a second source; a stale attribution survives its source's retraction |
| **S — Sharing & retraction** | Silent drift | A share reaches the wrong readers, misrepresents the sharer, or its retraction is not delivered as an event |
| **G — Growth** | Unbounded growth / silent loss | Read surface exceeds bound; a decision was lost to condensation; a drop was undiscoverable |
| **F — Forgetting** | Zombie memory | A superseded or retracted item is still shown, or comes back |
| **R — Recall** | Over-refusal (the other half) | A legitimate write never reaches an entitled reader |

Headline:

    governance   = min(C, A, T, E, S, G, F)      # the weakest failure mode
    contribution = R

Shown side by side, never combined.

## Reference adapters

- **`null`** — append everything, show everyone. Scores ~1.0 on R and fails
  every failure mode. Proves the measures bite.
- **`strata`** — the implementation the theory was first built for. One
  participant among others.

Cost (latency, calls to the system) is recorded per run as an appendix and
never scored.
