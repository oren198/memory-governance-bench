"""Run-file validation, shared by `fmb submit` and CI (SPEC.md §4/§5)."""

from __future__ import annotations

from bench import BENCH_VERSION, RELEASE_SEED
from bench.runner import CONTRIBUTION_FAMILY, GOVERNANCE_FAMILIES

REQUIRED = (
    "run_id", "bench_version", "timestamp", "seed", "repeat", "submittable",
    "system", "declarations", "headline", "families", "policy", "scenarios",
    "cost", "environment",
)
REQUIRED_SYSTEM = ("id", "name", "version")
REQUIRED_FAMILY = ("pass", "total", "rate", "wilson_low", "unsupported")
DECLARATION_KEYS = ("notes_flow_down", "listening_is_transitive", "multiple_containers")


def validate(run: dict, *, for_submission: bool = False) -> list[str]:
    """Return a list of problems; empty means valid."""
    problems: list[str] = []

    for key in REQUIRED:
        if key not in run:
            problems.append(f"missing top-level key: {key}")
    if problems:
        return problems

    for key in REQUIRED_SYSTEM:
        if not run["system"].get(key):
            problems.append(f"system.{key} is required and must be non-empty")
    for key in DECLARATION_KEYS:
        if key not in run["declarations"]:
            problems.append(f"declarations.{key} is missing")
        elif not isinstance(run["declarations"][key], bool):
            problems.append(f"declarations.{key} must be a boolean")

    for key in ("governance", "contribution"):
        value = run["headline"].get(key, "missing")
        if value is None:
            if run.get("submittable", False):
                problems.append(
                    f"headline.{key} is null but the run claims to be submittable"
                )
            continue   # a partial run honestly reports no headline
        if not isinstance(value, (int, float)) or not 0.0 <= value <= 1.0:
            problems.append(f"headline.{key} must be a number in [0,1], or null")

    for fam in GOVERNANCE_FAMILIES + (CONTRIBUTION_FAMILY,):
        block = run["families"].get(fam)
        if block is None:
            problems.append(f"families.{fam} is missing — every family must be reported")
            continue
        for key in REQUIRED_FAMILY:
            if key not in block:
                problems.append(f"families.{fam}.{key} is missing")
        if block.get("total", 0) <= 0:
            problems.append(f"families.{fam} has no scenarios")

    if not run["scenarios"]:
        problems.append("scenarios is empty")
    for s in run["scenarios"]:
        for key in ("id", "family", "passed", "unsupported"):
            if key not in s:
                problems.append(f"scenario {s.get('id', '?')} missing {key}")
                break

    # The headline must be derivable from the families block, so a published
    # result cannot claim a score its own scenarios do not support.
    governance = min((run["families"][f]["rate"] for f in GOVERNANCE_FAMILIES
                      if f in run["families"]), default=None)
    if (governance is not None and run["headline"]["governance"] is not None
            and abs(governance - run["headline"]["governance"]) > 1e-6):
        problems.append("headline.governance is not min() of the governance families")
    contribution = run["families"].get(CONTRIBUTION_FAMILY, {}).get("rate")
    if (contribution is not None and run["headline"]["contribution"] is not None
            and abs(contribution - run["headline"]["contribution"]) > 1e-6):
        problems.append("headline.contribution does not match families.R.rate")

    if for_submission:
        if run["bench_version"] != BENCH_VERSION:
            problems.append(
                f"bench_version {run['bench_version']} != this release {BENCH_VERSION}"
            )
        if run["seed"] != RELEASE_SEED:
            problems.append("seed is not the release seed — run is not submittable")
        if not run.get("submittable", False):
            problems.append("run is marked not submittable (partial or reseeded run)")

    return problems
