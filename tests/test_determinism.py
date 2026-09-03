"""Two runs against the same system state must produce the same score."""

from bench.adapter.null import NullMemory
from bench.canary import canary, sentence
from bench.runner import run


def _outcomes(result):
    return {s["id"]: s["passed"] for s in result.scenarios}


def test_two_runs_agree():
    first = run(NullMemory())
    second = run(NullMemory())
    assert _outcomes(first) == _outcomes(second)
    assert first.headline == second.headline
    assert first.families == second.families


def test_only_identity_differs():
    first, second = run(NullMemory()).to_json(), run(NullMemory()).to_json()
    for key in ("run_id", "timestamp", "cost"):
        first.pop(key), second.pop(key)
    assert first == second


def test_canaries_are_a_pure_function_of_the_seed():
    assert canary(1, "C1", 0, "note") == canary(1, "C1", 0, "note")
    assert canary(1, "C1", 0, "note") != canary(2, "C1", 0, "note")
    assert canary(1, "C1", 0, "note") != canary(1, "C1", 1, "note")
    assert canary(1, "C1", 0, "note") in sentence(1, "C1", 0, "note")


def test_a_different_seed_changes_content_but_not_outcomes():
    default = run(NullMemory())
    reseeded = run(NullMemory(), seed=999)
    assert _outcomes(default) == _outcomes(reseeded), (
        "measures must not depend on the particular canary strings"
    )
    assert reseeded.submittable is False
