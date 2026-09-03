"""The repository's most important test.

The null adapter has no governance at all. It must score ~1.0 on the
contribution half and FAIL every failure-mode family. If a family passes
null, that family's graders do not bite and they are wrong — the benchmark
would be handing out marks for nothing.
"""

from bench.adapter.null import NullMemory
from bench.runner import CONTRIBUTION_FAMILY, GOVERNANCE_FAMILIES, run


def test_null_fails_every_governance_family():
    result = run(NullMemory())
    for family in GOVERNANCE_FAMILIES:
        block = result.families[family]
        assert block["total"] > 0, f"family {family} ran no scenarios"
        assert block["rate"] < 1.0, (
            f"family {family} passed the ungoverned baseline "
            f"({block['pass']}/{block['total']}) — its graders do not bite"
        )


def test_null_scores_full_contribution():
    result = run(NullMemory())
    block = result.families[CONTRIBUTION_FAMILY]
    assert block["rate"] == 1.0, (
        "a memory that shows everyone everything must not lose contribution marks; "
        f"got {block['pass']}/{block['total']}"
    )


def test_headline_is_the_pair():
    result = run(NullMemory())
    assert result.headline["governance"] == min(
        result.families[f]["rate"] for f in GOVERNANCE_FAMILIES
    )
    assert result.headline["contribution"] == result.families[CONTRIBUTION_FAMILY]["rate"]
    assert result.headline["governance"] < result.headline["contribution"], (
        "the ungoverned baseline must be visibly lopsided"
    )


def test_every_measure_produces_checks():
    """A scenario that records no checks passes vacuously. None may."""
    result = run(NullMemory())
    empty = [s for s in result.scenarios
             if not s["checks"] and not s["unsupported"] and not s["skipped"]]
    assert not empty, f"scenarios with no checks: {[s['id'] for s in empty]}"


def test_no_scenario_errored():
    result = run(NullMemory())
    errored = [(s["id"], s.get("error")) for s in result.scenarios if s.get("error")]
    assert not errored, f"scenarios raised: {errored}"
