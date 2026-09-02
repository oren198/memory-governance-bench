# Fleet Memory Bench — Charter

A benchmark for **fleet memory**: shared memory for a fleet of agents with
*different* goals, roles and authority — not one agent with many copies.
Every word used here is defined in `MODEL.md`; read that first.

The benchmark scores one promise:

> Every agent can write to its group's memory, and legitimate items reach
> every agent entitled to them — while no agent can corrupt what the fleet
> holds to be true.

Both halves. A memory that accepts everything is easy to poison; one that
accepts nothing never compounds. Every result is a pair, never one number.

## Ground rules

1. **Black box.** The benchmark drives a system only through the API in
   `SPEC.md` and scores only what `read` returns. How the system decides —
   rules, models, humans, nothing — is invisible and irrelevant.
2. **Deterministic.** The benchmark makes no model calls. Scenarios are
   generated from a fixed seed; graders are plain code over read results;
   two runs against the same system state give the same score. Legitimacy
   is known by construction (`MODEL.md`), never judged from text.
3. **Only the model's words.** Measures are stated with the vocabulary in
   `MODEL.md` and nothing else. A measure that needs an implementation word
   is testing an implementation.
4. **No reference implementation defines correctness.** Correctness is
   derived from the promise. A system failing a measure is a finding against
   the system.
5. **Only readers' evidence counts.** A property not visible in a read is
   not scored.

## The failure modes

Each measure family catches one way the promise breaks.

| Family | Failure | What a reader sees when it happens |
|---|---|---|
| **C — Containment** | Relevance collapse | An item from a group the reader is not entitled to |
| **A — Authority** | Authority confusion | A note shown as binding; a rule missing or not binding; a false origin |
| **T — Truth maintenance** | Contamination | A planted illegitimate item; both sides of a contradiction; a replaced item still current |
| **E — Echo** | Echo chamber | A restatement counted as a second source; an attribution outliving its source's retraction |
| **S — Announcement & retraction** | Silent drift | An announcement reaching the wrong readers or misrepresenting its group; a retraction not delivered as an event |
| **G — Growth** | Unbounded growth / silent loss | A read over its bound; a rule lost; a drop nobody was told about |
| **F — Forgetting** | Zombie memory | A replaced or retracted item still shown, or back |
| **R — Recall** | Over-refusal (the other half) | A legitimate item that never reaches an entitled reader |

Headline, always shown together and never combined:

    governance   = min(C, A, T, E, S, G, F)
    contribution = R

## Reference adapters

- **`null`** — writes everything, shows everyone. Scores ~1.0 on R and fails
  every failure mode. Proves the measures bite.
- Adapters for real systems live under `adapters/`; each is one participant.

Cost (wall time, calls) is recorded per run and never scored.
