"""The other half of the control.

A benchmark whose measures nothing can satisfy is as useless as one
everything satisfies. The reference adapter implements MODEL.md plainly —
no model, no cleverness — and must score 1.0 on every family. When it does
not, either the reference is wrong or a measure demands something the model
never asked for, and both are bugs worth finding here rather than in
someone else's repository.
"""

from bench.adapter.null import NullMemory
from bench.adapter.reference import ReferenceMemory
from bench.runner import CONTRIBUTION_FAMILY, GOVERNANCE_FAMILIES, run


def test_reference_passes_every_family():
    result = run(ReferenceMemory())
    failures = [s["id"] for s in result.scenarios if not s["passed"] and not s["skipped"]]
    assert not failures, f"the plain implementation of the model fails: {failures}"
    assert result.headline == {"governance": 1.0, "contribution": 1.0}


def test_reference_supports_every_operation():
    result = run(ReferenceMemory())
    unsupported = [s["id"] for s in result.scenarios if s["unsupported"]]
    assert not unsupported, unsupported


def test_the_two_baselines_are_far_apart():
    """Every governance family must separate a governed memory from an
    ungoverned one — otherwise that family measures nothing."""
    governed = run(ReferenceMemory())
    ungoverned = run(NullMemory())
    for family in GOVERNANCE_FAMILIES:
        assert governed.families[family]["rate"] > ungoverned.families[family]["rate"], (
            f"family {family} does not distinguish governed memory from a free-for-all"
        )
    assert (governed.families[CONTRIBUTION_FAMILY]["rate"]
            == ungoverned.families[CONTRIBUTION_FAMILY]["rate"] == 1.0), (
        "contribution must not punish either baseline: both show legitimate items"
    )


def test_policy_conformance_tracks_the_declaration():
    """The reference declares the conservative position on every chosen rule
    and behaves accordingly; the null adapter declares the same and does not."""
    assert run(ReferenceMemory()).policy["rate"] == 1.0
    assert run(NullMemory()).policy["rate"] < 1.0
