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

Family **P — Policy conformance** is reported separately and is not part of
either number: it grades a system against the choices it declared, not
against a preferred answer (MODEL.md § "Forced by the promise, and
chosen"). Conforming to a declared choice earns a clean P; it does not
exempt the system from the forced rules, which still apply to everything the
wider choice makes the memory do.

Headline, always shown together and never combined:

    governance   = min(C, A, T, E, S, G, F)
    contribution = R

## Reference adapters

- **`null`** — writes everything, shows everyone. Scores ~1.0 on R and fails
  every failure mode. Proves the measures bite.
- Adapters for real systems live under `adapters/`; each is one participant.

Cost (wall time, calls) is recorded per run and never scored.

## Known limitations

**The model shares an ancestry with one of the systems it grades.** This
model was written by the same hand that wrote the theory behind Strata, the
first reference adapter. Where the two agree, that agreement is not
independent evidence: the benchmark can show that a system implements the
model faithfully, not that the model is the only right one. Two things
follow, and both are load-bearing:

1. `MODEL.md` separates what the promise **forces** from what it merely
   **chooses**. Only the forced part is scored as governance. Every chosen
   rule is declared by the system under test and graded against its own
   declaration, so a system with a different — and defensible — stance is
   not marked down for holding it.
2. Several measures exist because building the benchmark forced questions
   the theory had not answered — what a reader is owed when memory is
   condensed away (G3) is still only partly settled, and the rules for
   retraction-as-event (S4) and attribution outliving its source (E2, E3)
   were written into the theory only after adversarial cases like these
   demanded them. A benchmark that can push back on its own theory is worth
   building; one that only restates it is not.

Contributions that argue a forced rule is actually a chosen one, or the
reverse, are the most valuable thing this repository can receive.

**Results are self-reported.** Runs are produced by the team being measured
and published by pull request. The audit trail is the run file and the PR
history, not an independent execution.

**Nondeterministic systems.** The benchmark is deterministic; a system under
test need not be. A system that decides with a model will see its scores
vary between runs. That variance is the system's property and the benchmark
reports it (`--repeat N` records the spread) rather than hiding it.

This reaches further than it first appears. It is tempting to sort the
families into ones a model touches and ones it does not, but the benchmark
cannot draw that line from outside: staying within a bound is plumbing in
one system and a judgment call in the next, and the same is true of deciding
what a rule conflicts with or what a claim is about. The benchmark grades
the read, not the mechanism behind it, so a measure is never disqualified
because a system chose to implement it with a model. What varies is the
confidence of a single run, which is why a published result covering a
model-driven system should carry a spread and not one number.
