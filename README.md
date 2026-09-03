# Fleet Memory Bench

**A benchmark for shared memory used by a fleet of agents with different
goals, roles and authority.**

> **Status: specification.** The measures are written; the code is not.
> There is no package, runner or adapter yet. See [Roadmap](#roadmap).

Most agent-memory work measures one agent remembering its own past. A fleet
is a different problem: many agents, different jobs, different authority,
writing into memory the others will act on. Then memory needs *governance* —
because the first agent to write nonsense poisons everyone else's work, and
a memory nobody may write to never compounds.

This benchmark scores exactly that trade-off:

> Every agent can write to its group's memory, and legitimate items reach
> every agent entitled to them — **while** no agent can corrupt what the
> fleet holds to be true.

Two numbers, always reported together and never combined:

```
governance   = min(C, A, T, E, S, G, F)   # the weakest failure mode
contribution = R                          # legitimate items that landed
```

A memory that refuses everything scores 1.0 on governance and 0.0 on
contribution. A memory that accepts everything scores the reverse. Neither
is a fleet memory.

## What is measured

| | Catches | Example scenario |
|---|---|---|
| **C** Containment | Relevance collapse | Sales writes a note; Support must not be shown it |
| **A** Authority | Authority confusion | A company-wide rule reaches an agent three levels down, in full, marked binding |
| **T** Truth maintenance | Contamination | Two agents report opposite results; the fleet holds one or neither, never both |
| **E** Echo | Echo chambers | A rumour crossing three teams must not come back as "everyone agrees" |
| **S** Announcement & retraction | Silent drift | Billing retracts a claim; every team it reached is *told*, not left to notice |
| **G** Growth | Unbounded growth | Reads stay within their bound, rules are never what gets dropped |
| **F** Forgetting | Zombie memory | Retracted and replaced items leave, and do not come back |
| **R** Recall | Over-refusal | A legitimate note reaches the agents entitled to it |
| **P** Policy | *(not scored)* | Systems declare their design choices and are graded against their own declaration |

Full list with justification for each: **[MEASURES.md](MEASURES.md)**.

## How it works

- **Black box.** A system is driven through seven HTTP endpoints and scored
  only on what `read` returns. Rules engine, model, database, human
  moderator — the benchmark cannot tell and does not care.
- **Deterministic.** No model calls anywhere in the benchmark. Legitimacy is
  a fact it constructs (it built the fleet, it knows who wrote what and what
  contradicts what), never an opinion formed by reading text. Graders match
  canary tokens.
- **No implementation vocabulary.** Every term is defined from nothing in
  [MODEL.md](MODEL.md) — groups, notes, rules, announcements — and no other
  word may appear in a measure.
- **Forced vs chosen.** Rules the promise genuinely forces are scored as
  governance. Rules that are defensible either way (does a container's
  working memory reach its teams? how far do announcements travel?) are
  *declared* by the system and graded against its own declaration. A team
  that disagrees with the model can still be scored fairly.

## Documents

| | |
|---|---|
| **[MODEL.md](MODEL.md)** | Every term, defined from nothing, with a worked example. Start here. |
| **[CHARTER.md](CHARTER.md)** | What the benchmark is for, its ground rules, and its known limitations. |
| **[MEASURES.md](MEASURES.md)** | Every scenario: what it tests, why it matters to a fleet, the justification. |
| **[SPEC.md](SPEC.md)** | The API a system implements, determinism rules, result format, publishing, UI. |

## Participating (once the runner exists)

```bash
fmb run    --system http://localhost:8080   # your system, any language
fmb ui                                      # dashboard: your runs and published ones
fmb submit <run-id>                         # opens a PR adding your result
```

Results are published to this repository by pull request and rendered as a
leaderboard on the governance × contribution plane, plus per-system history
so a team can measure itself against its own earlier versions.

## Roadmap

1. Runner, family **C**, and the `null` adapter — a deliberately naive
   append-everything memory that must *fail* the measures, proving they bite.
2. Remaining families.
3. Real adapters, then the UI and result submission.

## Honesty about where this came from

This model was written by the same author as the theory behind
[Strata](https://github.com/oren198/Strata), which will be one of the first
adapters. Where the two agree, that agreement is not independent evidence.
Two safeguards: only rules the promise *forces* are scored as governance
(everything else is declared and graded against the declaration), and the
benchmark deliberately includes measures whose right answer the theory did
not settle in advance. Strata is expected to fail some of them, and those
results will be published as they fall.

**The most valuable contribution this repository can receive is an argument
that a rule it calls forced is actually a choice, or the reverse.**

## License

MIT — see [LICENSE](LICENSE).
