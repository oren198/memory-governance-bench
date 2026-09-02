# Memory Governance Bench — Charter

A benchmark for **governed shared memory**: memory that many agents write to
and read from, where the system — not the writers — decides what the group
holds to be true.

It measures one promise:

> Every agent can contribute to shared memory **without** any agent being
> able to corrupt what the group collectively holds to be true.

A system that is easy to write to and easy to poison does not keep the
promise. Neither does one so locked down that nothing compounds. Every
measure here scores one side of that tension, and the report always shows
both sides next to each other, because a system can trivially max either one
alone.

## What is being tested, and what is not

The benchmark is **black-box**. It observes a system only through what agents
can do to it (write, retract, share, read) and what they get back (what a
reader in a given place is shown). It makes no assumption about *how* the
system decides — an LLM judge, a rules engine, a vector store with filters, a
human moderator, or nothing at all are all valid systems under test. Any
measure that can only be scored by looking inside a system is out of scope by
construction.

Consequently the benchmark never uses, and adapters must never require, the
vocabulary of any one implementation: "judge", "summary", "prompt",
"embedding", "amendment" do not appear in a measure. If a measure cannot be
stated without such a word, it is testing an implementation, not the promise.

## The promise, decomposed

Governed memory has to hold five properties at once. Each is a named failure
mode, and each measure below is scored against exactly one of them.

| Failure mode | The promise broken | What the reader sees |
|---|---|---|
| **Contamination** | Something false, stale, or malicious becomes part of what the group holds | A reader is shown an item that should not be there |
| **Echo chamber** | One source's claim, repeated, is mistaken for independent corroboration | A claim is promoted on the strength of copies of itself |
| **Authority confusion** | A reader cannot tell what binds them from what merely informs them, or who said what | Observation and decision blur; attribution is missing or wrong |
| **Relevance collapse** | Everything is shown to everyone; the signal is lost | A reader in one place is shown material that belongs to another |
| **Unbounded growth** | Memory only accumulates | The read surface grows without limit, or shrinks silently |

And the other half of the tension, without which the first five are free:

| Property | The promise | What the reader sees |
|---|---|---|
| **Contribution** | A legitimate observation from any agent can reach the readers it is relevant to | A true, relevant item written in one place is shown to the readers who should have it |

A system that declines everything scores perfectly on the five failure modes
and zero on contribution. The headline is always the pair.

## The world the benchmark assumes

To be general, the benchmark assumes only what the promise itself needs:

- **Agents** write and read. An agent acts *from* a place.
- **Places** (scopes) are where memory lives. A place has readers who are
  entitled to what it holds; others are not. Places can **contain** other
  places (a team inside a department inside an organisation), and a place
  can **refer** to a peer place it wants to hear from.
- Two **kinds** of memory item exist and behave differently:
  - an **observation** — something an agent saw; informs, does not bind;
  - a **decision** — something an authority settled; binds every reader in
    the places it covers.
- An **authority** for a place is whoever may make decisions for it.
  A containing place's decisions bind the places it contains; the reverse
  is never true.
- An **operator** — a human or process standing outside the agents — may
  make decisions that bind a place directly.
- **Sharing** is the act by which memory held in one place is offered to
  readers in another. It is distinct from containment: what a contained
  place inherits is what *binds* it, not the container's working memory.
- **Retraction** is the act of taking back something previously written or
  shared.

These are the concepts of the underlying theory (see `PHILOSOPHY.md`) stated
without any mechanism. A system need not use these words internally; the
adapter maps them.

## Measure families

Each family is one failure mode (or the contribution side) and contains
scenarios that are graded from read results alone.

| Family | Scores | Deterministic? |
|---|---|---|
| **C — Containment** | Relevance collapse: an item written in one place is never shown to a reader not entitled to it (sibling, unrelated branch, child-to-parent leak, container context leaking downward) | Yes — canary strings |
| **A — Authority** | Authority confusion: decisions bind and are shown as binding; observations inform and are shown as informing; a decision from a containing place is shown to every contained reader in full; an observation never displaces a decision; every item a reader sees says where it came from, and that label is true | Yes |
| **T — Truth maintenance** | Contamination: false, malicious, injected, or self-contradicting writes do not become what readers are shown; a reader is never shown both sides of a contradiction as if both held; a later correction replaces the earlier claim | Mixed — golden datasets with labelled writes; a benchmark-owned grader for coherence |
| **E — Echo** | Echo chamber: a claim shared by A and restated by B is not counted as two sources; when A retracts, B's restatement either stands on B's own evidence or goes; attribution to a source that has retracted does not persist as if the source still held it | Yes for attribution lifecycle; grader for corroboration |
| **S — Sharing & retraction** | Sharing reaches exactly the readers it was offered to and no further; what is shared is faithful to what the sharer holds; a retraction reaches every reader the share reached, and reaches them as an event (a reader can tell something was withdrawn, and what) — not as silent absence | Yes |
| **G — Growth** | Unbounded growth: the read surface stays within a stated bound as writes accumulate; when the system drops or condenses to stay bounded, binding decisions are never lost, and what was dropped is discoverable (the system did not silently forget) | Yes |
| **R — Recall (contribution side)** | A true, relevant, non-conflicting observation written by any agent is shown to entitled readers within N reads; the fraction of legitimate writes that ever reach a reader | Yes |
| **F — Forgetting** | Obsolete items leave the read surface once superseded or retracted, within N reads; nothing retired reappears | Yes |

Cost (tokens, latency, dollars) is reported as an appendix, never scored.

## How a system participates

A system implements the adapter (`bench/adapter/protocol.py`): set up a
world, write, retract, share, unshare, read, and `settle()` — a hook that
lets the system finish whatever asynchronous work it does between a write and
the next read. That is the entire surface. If a system cannot implement an
operation (no sharing channel, no retraction), the adapter says so and the
corresponding scenarios are reported **unsupported**, which is scored as the
failure it is — a memory that cannot retract cannot keep the promise — but is
labelled distinctly so the reader of the report knows why.

Two adapters ship with the benchmark:

- **`null`** — a naive append-everything, show-everyone memory. It scores
  100% on contribution and fails every failure mode. Its purpose is to prove
  the measures bite.
- **`strata`** — the reference implementation the theory was first built
  for. It is one participant, not the definition of correctness; a measure
  that Strata fails is a finding against Strata, never a reason to change the
  measure.

## Scoring

Each scenario yields pass/fail (or a fraction, for population measures).
Families report a rate with a Wilson 95% lower bound; thresholds are stated
per family in `thresholds.yaml`. The headline is a two-number pair:

    governance = min over the five failure-mode families
    contribution = R

reported together and never combined into one scalar.

## What the benchmark refuses to do

- Score anything not visible to a reader.
- Reward a mechanism. Two systems that show readers the same things score
  the same, however they got there.
- Let any system under test — including the reference one — define what
  correct is. Correctness is derived from the promise, in this document.
- Grade with the system's own model. Where a grader must read prose (is this
  a contradiction? is this the same claim?), the grader belongs to the
  benchmark, is fixed per release, and is applied identically to every
  system.
