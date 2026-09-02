# Strata adapter (not built yet)

Notes from the Strata architect, recorded before writing a line of it.

## Do not drive Strata through its CLI or a running server

A benchmark run calls `/world` hundreds of times, each wiping all memory.
Driving that through `strata start` or the CLI is dangerous: a test run on
this machine reached the operator's **real** store and destroyed real
memory. Strata's own isolation guard only protects processes that load its
`conftest`; the adapter is not one of those.

Build the adapter **in-process against the library**, with every path
explicit: `FleetConfig.load(<tmp>/fleet.yaml)`, an explicit db path and
`summaries_dir`, a fresh temp directory per scenario, migrations run there.

## Mapping

| Benchmark | Strata |
|---|---|
| group | scope |
| part of | chain edge |
| listens to | reference edge |
| owner group | scope the operator attaches memory to |
| origin / via | `origin_scope_id` / `relay_scope_id` (ADR 0013 D4) |

## Known gaps — expect these to fail or report `unsupported`

- **`event: "withdrawn"`** — no equivalent. Strata withdraws by removing the
  item from the published face; the next read simply lacks it, and there is
  no record of who was previously shown it. Family S will fail for a real
  reason (Strata#186).
- **`attributed_to`** — partial. Attribution lives in prose ("according to
  X") plus D4b's cascade withdrawal, not in a structured field. Graders that
  read the field fail; graders that test the cascade behaviour should pass.
- **Retracting a note** — no equivalent. Retirement exists for directives
  only; context is dropped when the summary is next rewritten, not retracted.
- **Multiple containers** — a scope has at most one chain parent, so Strata
  declares `multiple_containers: false`.
- **Adjacent strata only** — chain edges are legal only between adjacent
  strata, so `part_of` depth must map onto stratum ordinals; arbitrary
  containment DAGs are not expressible.
- **Nondeterminism and cost** — write and announce go through an LLM judge.
  Scores will vary between runs (use `--repeat`) and a full run costs judge
  tokens.
