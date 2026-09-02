# Specification

Precise contract: how a team runs the benchmark, what their system must
expose, what a result is, and how results are published and compared.

## 1. Running it

```
pip install fleet-memory-bench            # or: pip install -e .
fmb run  --system mypkg.adapter:MySystem   # Python adapter, or
fmb run  --system http://localhost:8080    # HTTP adapter (any language)
fmb run  ... --families C,A,T              # subset while iterating
fmb ui                                     # local dashboard: your runs + published ones
fmb submit <run-id>                        # publish one run to this repo
```

`fmb run` writes one **run file** to `~/.fmb/runs/<run-id>.json` and prints
the headline pair. Run as many times as you like; nothing leaves your machine
until `fmb submit`.

## 2. The system API

A system participates by exposing five operations plus setup. Two bindings
carry the same contract; the HTTP binding is canonical and the Python
binding is a convenience.

### 2.1 HTTP binding (canonical)

All bodies are JSON. The benchmark is the only client; the system is a
server. Every request carries the acting agent.

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/world` | `World` | `{}` — replace the topology; wipe all memory |
| `POST` | `/write` | `{actor, content, kind, supersedes?, subject?}` | `Receipt` |
| `POST` | `/retract` | `{actor, receipt_id}` | `Receipt` |
| `POST` | `/share` | `{actor, receipt_id}` | `Receipt` — offer a held item outward |
| `POST` | `/unshare` | `{actor, receipt_id}` | `Receipt` |
| `POST` | `/read` | `{actor}` | `ReadResult` |
| `POST` | `/settle` | `{}` | `{}` — finish deferred work; return when a `read` would be stable |
| `GET` | `/info` | — | `{id, name, version}` |

Unsupported operation: respond `501` with `{"unsupported": "<op>"}`.

**Types**

```
World      { scopes: [id], contains: [[outer, inner]], refers: [[scope, peer]],
             operator_scopes: [id] }
Actor      { id, scope, operator: bool }
kind       "observation" | "decision"
Receipt    { id, accepted: bool, reason?: string }
ReadResult { items: [Shown], words: int }
Shown      { content, kind, origin, binding: bool,
             via?: scope, attributed?: scope, receipt?: id,
             event?: "withdrawn" }
```

`Shown` is the unit every measure grades:

- `content` — text as shown to the reader.
- `kind` — how the reader is told to treat it.
- `binding` — whether the reader is told it binds them.
- `origin` — the scope the system says it came from. Must be true.
- `via` — set when the item reached the reader through an intermediate scope.
- `attributed` — set when the item restates another scope's claim.
- `receipt` — the write/share it derives from, when the system can say.
- `event` — `"withdrawn"` when the reader is being told this item was
  retracted. A withdrawn item is shown once as an event, then may vanish.

`words` — the size of what the reader was shown, counted by the system
(whitespace-split). Family G uses it against the bound the scenario states.

### 2.2 Python binding

`bench.adapter.MemorySystem` (`bench/adapter/protocol.py`) — the same seven
operations as methods. The benchmark wraps a Python adapter and an HTTP
endpoint identically.

### 2.3 What the benchmark promises the system

- `setup`/`/world` is called once per scenario; scenarios are independent.
- `settle` is called after every batch of writes and before every read.
  Systems that decide synchronously implement it as a no-op.
- The benchmark never calls the system concurrently within a scenario unless
  the scenario says so (family T has explicit concurrent-write cases).
- Content strings contain **canaries** — unique tokens per scenario per
  item. Graders look for canaries in `read` output; they never interpret
  prose. This is what makes the benchmark deterministic.

## 3. Determinism

- Every scenario is generated from `(bench_version, family, index, seed)`.
  The seed is fixed per benchmark release; `--seed` may override it for
  robustness checks but such runs are not submittable.
- Graders are pure functions of `ReadResult`s. No model, no network, no
  clock. Contradictions are constructed structurally (same `subject`,
  canary-tagged opposing values), never detected by reading prose.
- A run file records the exact scenario ids and grader version, so any run
  is reproducible from the file alone.

## 4. Run file

```
{
  "run_id":        "<uuid>",
  "bench_version": "0.1.0",
  "timestamp":     "<ISO-8601 UTC>",
  "system":        { "id": "<slug>", "name": "...", "version": "...",
                     "url": "...", "notes": "..." },
  "headline":      { "governance": 0.83, "contribution": 0.97 },
  "families":      { "C": {"pass": 118, "total": 120, "rate": .983,
                           "wilson_low": .95, "unsupported": 0}, ... },
  "scenarios":     [ {"id": "C-007", "family": "C", "passed": true,
                      "unsupported": false, "detail": {...}} ... ],
  "cost":          { "wall_seconds": 412, "calls": 9381 },
  "environment":   { "python": "...", "platform": "..." }
}
```

`system.id` is the stable identity across versions (comparison-to-self keys
on it). `system.version` is whatever the team versions by.

## 5. Publishing a result

`fmb submit <run-id>`:

1. Validates the run file (schema, seed is the release seed, all families
   present or explicitly `unsupported`).
2. Writes it to `results/<system-id>/<timestamp>.json` on a branch and opens
   a pull request against this repository (via `gh`; falls back to printing
   the file and the PR URL to create manually).
3. CI on the PR re-validates the file. Merging publishes it.

No credentials beyond the submitter's own GitHub account. Results are
self-reported and the PR history is the audit trail.

The UI's **Submit** button runs the same flow for the selected local run.

## 6. UI

Static site, built from `results/**.json` at deploy time and served from
GitHub Pages at the repo's URL; `fmb ui` serves the same site locally with
your unsubmitted runs merged in.

Views:

- **Leaderboard** — every system's latest submitted run, plotted on the
  governance × contribution plane. A point in the top-right is the goal;
  the axes are never merged.
- **System** — one system over time (comparison to self): headline pair per
  version, per-family trend, scenario-level diff between any two runs.
- **Compare** — two or more systems side by side by family, with the
  scenario-level diff for a chosen family.
- **Scenario** — what a scenario does and which systems fail it.

Local runs appear with a "not submitted" badge until published.

## 7. Versioning

Scenarios, seeds and graders are frozen per `bench_version`. Results are
comparable only within a major version; the UI groups by it. A change to a
scenario or grader is a new benchmark version, never an edit in place.
