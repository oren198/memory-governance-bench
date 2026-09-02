# Specification

How a team runs the benchmark, what their system must expose, what a result
is, and how results are published and compared. Vocabulary: `MODEL.md`.

## 1. Running it

```
pip install fleet-memory-bench            # or: pip install -e .
fmb run  --system http://localhost:8080   # HTTP adapter (any language)
fmb run  --system mypkg.adapter:MySystem  # Python adapter
fmb run  ... --families C,A,T             # subset while iterating
fmb run  ... --repeat 5                   # repeat every scenario; record the spread
fmb ui                                    # local dashboard: your runs + published ones
fmb submit <run-id>                       # publish one run to this repo
```

`fmb run` writes one run file to `~/.fmb/runs/<run-id>.json` and prints the
headline pair. Nothing leaves your machine until `fmb submit`.

## 2. The system API

The benchmark is the only client; the system is a server. The HTTP binding
is canonical; the Python binding (`bench/adapter/protocol.py`) is the same
contract as methods.

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/world` | `World` | `{}` — replace the fleet; wipe all memory |
| `POST` | `/write` | `{agent, content, kind, replaces?, subject?}` | `Receipt` |
| `POST` | `/announce` | `{agent, receipt_id}` | `Receipt` |
| `POST` | `/retract` | `{agent, receipt_id}` | `Receipt` — a write or an announcement |
| `POST` | `/read` | `{agent}` | `Read` |
| `POST` | `/settle` | `{}` | `{}` — finish deferred work; return when reads are stable |
| `GET` | `/info` | — | `{id, name, version, declarations}` |

Unsupported operation: `501` with `{"unsupported": "<op>"}`.

**Types**

```
World    { groups: [id], part_of: [[group, container]], listens_to: [[group, source]],
           owner_groups: [id] }
Agent    { id, group, owner: bool }
kind     "note" | "rule"
Receipt  { id, accepted: bool, reason?: string }
Read     { items: [Shown], words: int }
Shown    { content, kind, origin, binding: bool,
           via?: group, attributed_to?: group, receipt?: id,
           event?: "withdrawn" }
```

`Shown` fields mean exactly what `MODEL.md` § "What a reader is shown" says.
`words` is the size of the read, whitespace-split, counted by the system.

**Declarations.** `/info` returns a `declarations` object stating the
system's position on each rule the promise does not force (MODEL.md
§ "Forced by the promise, and chosen"):

```
declarations { notes_flow_down: bool,          // container notes shown to its parts
               listening_is_transitive: bool,  // announcements travel past one hop
               multiple_containers: bool }     // a group may be part of several
```

Family P grades the system against these values and nothing else: a
declaration is never wrong, only unmet. Missing keys default to `false`.
Declarations are recorded in the run file and shown in the UI beside the
score, so a reader knows which fleet shape was measured.

**What the benchmark promises the system**

- `/world` is called once per scenario; scenarios are independent.
- `/settle` is called after every batch of writes and before every read.
  A system that decides synchronously implements it as a no-op.
- The system is not called concurrently within a scenario unless the
  scenario says so (family T has explicit concurrent cases).
- Every content string contains a **canary** — a token unique to that item
  in that scenario. Graders look for canaries in reads; they never
  interpret prose.

## 3. Determinism

- A scenario is a pure function of `(bench_version, family, index, seed)`.
  The seed is fixed per release; `--seed` overrides for robustness checks
  but such runs are not submittable.
- Graders are pure functions of reads. No model, no network, no clock.
- A run file records scenario ids and grader version; any run is
  reproducible from the file alone.

## 4. Run file

```
{
  "run_id":        "<uuid>",
  "bench_version": "0.1.0",
  "timestamp":     "<ISO-8601 UTC>",
  "system":        { "id": "<slug>", "name": "...", "version": "...",
                     "url": "...", "notes": "..." },
  "headline":      { "governance": 0.83, "contribution": 0.97 },
  "declarations":  { "notes_flow_down": false, "listening_is_transitive": false,
                     "multiple_containers": false },
  "policy":        { "pass": 12, "total": 12 },
  "families":      { "C": {"pass": 118, "total": 120, "rate": .983,
                           "wilson_low": .95, "unsupported": 0}, ... },
  "scenarios":     [ {"id": "C1-007", "family": "C", "passed": true,
                      "unsupported": false, "detail": {...}} ... ],
  "cost":          { "wall_seconds": 412, "calls": 9381 },
  "environment":   { "python": "...", "platform": "..." }
}
```

`system.id` is the stable identity across versions; `system.version` is
whatever the team versions by.

## 5. Publishing a result

`fmb submit <run-id>` (or the UI's **Submit** button):

1. Validates the run file (schema; release seed; every family present or
   explicitly unsupported).
2. Writes it to `results/<system-id>/<timestamp>.json` on a branch and opens
   a pull request against this repository via `gh`; without `gh`, prints
   the file and the URL to open the PR by hand.
3. CI re-validates on the PR. Merging publishes it.

Results are self-reported; the PR history is the audit trail.

## 6. UI

Static site built from `results/**.json`, served from GitHub Pages;
`fmb ui` serves the same site locally with unsubmitted runs merged in and
badged "not submitted".

- **Leaderboard** — each system's latest run on the governance ×
  contribution plane. Axes are never merged.
- **System** — one `system.id` over versions: headline per version,
  per-family trend, scenario-level diff between any two runs.
- **Compare** — several systems side by side by family, with a
  scenario-level diff for a chosen family.
- **Scenario** — what it does, which systems fail it.

## 7. Versioning

Scenarios, seeds and graders are frozen per `bench_version`. Results
compare only within a major version; the UI groups by it. A change to a
scenario or grader is a new version, never an edit in place.
