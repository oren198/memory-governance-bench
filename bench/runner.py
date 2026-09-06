"""Executes scenarios and assembles a run file (SPEC.md §4)."""

from __future__ import annotations

import platform
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bench import BENCH_VERSION, RELEASE_SEED
from bench.adapter.protocol import Declarations, MemorySystem
from bench.scenario import VARIANTS, ScenarioResult, registry, run_scenario
from bench.stats import median, rate, wilson_lower

# Families whose failures are governance failures. P is policy conformance
# (reported, not scored) and R is the contribution half of the promise.
GOVERNANCE_FAMILIES = ("C", "A", "T", "E", "S", "G", "F")
CONTRIBUTION_FAMILY = "R"
POLICY_FAMILY = "P"


@dataclass
class Run:
    run_id: str
    bench_version: str
    timestamp: str
    seed: int
    repeat: int
    submittable: bool
    system: dict
    declarations: dict
    headline: dict
    families: dict
    policy: dict
    scenarios: list[dict]
    cost: dict
    environment: dict
    notes: list[str] = field(default_factory=list)
    # `notes` is the runner's own account of why a run is what it is; `remarks`
    # is the team's, and the two are kept apart so a team cannot write a line
    # that reads as the benchmark's verdict on its own run.
    remarks: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "run_id": self.run_id,
            "bench_version": self.bench_version,
            "timestamp": self.timestamp,
            "seed": self.seed,
            "repeat": self.repeat,
            "submittable": self.submittable,
            "system": self.system,
            "declarations": self.declarations,
            "headline": self.headline,
            "families": self.families,
            "policy": self.policy,
            "scenarios": self.scenarios,
            "cost": self.cost,
            "environment": self.environment,
            "notes": self.notes,
            "remarks": self.remarks,
        }


def _family_block(results: list[ScenarioResult]) -> dict:
    scored = [r for r in results if not r.skipped]
    total = len(scored)
    passed = sum(1 for r in scored if r.passed)
    return {
        "pass": passed,
        "total": total,
        "rate": round(rate(passed, total), 6),
        "wilson_low": round(wilson_lower(passed, total), 6),
        "unsupported": sum(1 for r in scored if r.unsupported),
        "skipped": sum(1 for r in results if r.skipped),
    }


def run(
    system: MemorySystem,
    families: list[str] | None = None,
    seed: int = RELEASE_SEED,
    repeat: int = 1,
    timeout: float | None = 120.0,
    progress=None,
    remarks: list[str] | None = None,
) -> Run:
    info = system.info()
    declarations: Declarations = info.declarations
    measures = registry()
    wanted = [m for m, (fam, _doc, _fn) in sorted(measures.items())
              if families is None or fam in families]

    started = time.time()
    passes: list[list[ScenarioResult]] = []
    for attempt in range(repeat):
        results: list[ScenarioResult] = []
        for measure in wanted:
            for variant in range(VARIANTS):
                result = run_scenario(
                    system, measure, variant, seed, declarations, timeout=timeout
                )
                results.append(result)
                if progress:
                    progress(result, attempt)
        passes.append(results)
    elapsed = time.time() - started

    # The first pass is the reported one; repeats measure stability only.
    primary = passes[0]
    by_family: dict[str, list[ScenarioResult]] = {}
    for r in primary:
        by_family.setdefault(r.family, []).append(r)

    # Every family that ran is recorded, P included. "Not scored" governs the
    # HEADLINE only: P is excluded from the min() below, never from the record.
    # A P result is the evidence a system's declaration was checked rather than
    # merely repeated, so a run file that omits it hides the wrong thing.
    families_block = {fam: _family_block(rs) for fam, rs in sorted(by_family.items())}
    policy_block = families_block.get(POLICY_FAMILY, _family_block([]))

    # A family that was not run has no rate. Reporting it as 0.0 would be a
    # score the run never earned, and indistinguishable from a real failure,
    # so a partial run carries `null` and the dashboard shows a dash.
    missing_governance = [f for f in GOVERNANCE_FAMILIES if f not in families_block]
    governance = (
        None if missing_governance
        else min(families_block[f]["rate"] for f in GOVERNANCE_FAMILIES)
    )
    contribution = (
        families_block[CONTRIBUTION_FAMILY]["rate"]
        if CONTRIBUTION_FAMILY in families_block else None
    )

    notes: list[str] = []
    if seed != RELEASE_SEED:
        notes.append("seed overridden — not submittable")
    timed_out = [r.id for r in primary if (r.reason or "").startswith("timeout")]
    if timed_out:
        notes.append(f"{len(timed_out)} scenario(s) timed out after {timeout}s")
    if families is not None:
        notes.append(f"partial run: families {','.join(sorted(families))} — not submittable")

    if repeat > 1:
        unstable = 0
        outcomes: dict[str, set[bool]] = {}
        for results in passes:
            for r in results:
                outcomes.setdefault(r.id, set()).add(r.passed)
        unstable = sum(1 for v in outcomes.values() if len(v) > 1)
        for fam in families_block:
            rates = []
            for results in passes:
                rs = [r for r in results if r.family == fam and not r.skipped]
                rates.append(rate(sum(1 for r in rs if r.passed), len(rs)))
            families_block[fam]["spread"] = {
                "min": round(min(rates), 6),
                "median": round(median(rates), 6),
                "max": round(max(rates), 6),
            }
        families_block_unstable = unstable
        notes.append(f"{unstable} scenario(s) unstable across {repeat} repeats")
    else:
        families_block_unstable = 0

    calls = getattr(system, "calls", None)
    return Run(
        run_id=str(uuid.uuid4()),
        bench_version=BENCH_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        seed=seed,
        repeat=repeat,
        submittable=(seed == RELEASE_SEED and families is None),
        system={
            "id": info.id,
            "name": info.name,
            "version": info.version,
        },
        declarations={
            "notes_flow_down": declarations.notes_flow_down,
            "listening_is_transitive": declarations.listening_is_transitive,
            "multiple_containers": declarations.multiple_containers,
        },
        headline={
            "governance": None if governance is None else round(governance, 6),
            "contribution": None if contribution is None else round(contribution, 6),
        },
        families=families_block,
        policy=policy_block,
        scenarios=[r.to_json() for r in primary],
        cost={
            "wall_seconds": round(elapsed, 3),
            "calls": calls,
            "timeout_seconds": timeout,
            "timed_out": len(timed_out),
            "unstable_scenarios": families_block_unstable,
        },
        environment={
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        notes=notes,
        remarks=list(remarks or []),
    )
