"""Run files must match SPEC.md §4, and `submit` must refuse what CI would."""

import json

import pytest

from bench.adapter.null import NullMemory
from bench.runner import run
from bench.schema import validate


@pytest.fixture()
def valid_run():
    return run(NullMemory()).to_json()


def test_a_fresh_run_validates(valid_run):
    assert validate(valid_run) == []
    assert validate(valid_run, for_submission=True) == []


def test_missing_family_is_rejected(valid_run):
    valid_run["families"].pop("S")
    problems = validate(valid_run)
    assert any("families.S is missing" in p for p in problems)


def test_headline_must_match_the_families(valid_run):
    valid_run["headline"]["governance"] = 1.0
    assert any("min()" in p for p in validate(valid_run))


def test_partial_run_is_not_submittable():
    result = run(NullMemory(), families=["C"])
    assert result.submittable is False
    assert any("not submittable" in p for p in validate(result.to_json(), for_submission=True))


def test_reseeded_run_is_not_submittable():
    result = run(NullMemory(), seed=4242)
    assert any("release seed" in p for p in validate(result.to_json(), for_submission=True))


def test_declarations_are_recorded(valid_run):
    assert set(valid_run["declarations"]) == {
        "notes_flow_down", "listening_is_transitive", "multiple_containers"
    }


def test_run_file_round_trips(valid_run, tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps(valid_run))
    assert validate(json.loads(path.read_text())) == []


def test_partial_run_reports_no_headline():
    """A family that was never run has no rate. Reporting 0.0 would be a score
    the run did not earn, and would read on the dashboard as a total failure."""
    result = run(NullMemory(), families=["C"])
    assert result.headline["governance"] is None
    assert result.headline["contribution"] is None
    assert validate(result.to_json()) == []


def test_a_null_headline_cannot_claim_to_be_submittable():
    result = run(NullMemory(), families=["C"]).to_json()
    result["submittable"] = True
    problems = validate(result)
    assert any("submittable" in p for p in problems)


def test_policy_family_is_in_the_record():
    """P is excluded from the headline, never from the file. Its result is the
    evidence a system's declaration was checked rather than merely repeated."""
    result = run(NullMemory()).to_json()
    assert "P" in result["families"], "family P must be recorded like any other"
    assert result["families"]["P"]["total"] > 0
    assert result["policy"] == result["families"]["P"], (
        "the policy key is a convenience alias for families.P and must agree"
    )


def test_families_and_scenarios_reconcile():
    """Summing family totals and counting scenarios must give one answer."""
    result = run(NullMemory()).to_json()
    counted = sum(b["total"] + b["skipped"] for b in result["families"].values())
    assert counted == len(result["scenarios"]), (
        f"families account for {counted}, scenarios[] holds {len(result['scenarios'])}"
    )


def test_a_missing_family_breaks_reconciliation():
    result = run(NullMemory()).to_json()
    result["families"].pop("P")
    assert any("a family is missing from the record" in p for p in validate(result))


def test_a_skipped_scenario_is_neither_pass_nor_fail():
    """A scenario a system's declaration puts out of scope did not pass; it
    was never asked. Recording it as passed inflates the count silently."""
    result = run(NullMemory()).to_json()
    skipped = [s for s in result["scenarios"] if s["skipped"]]
    assert skipped, "the null adapter declares a tree, so P3 is not applicable"
    assert all(s["passed"] is None for s in skipped)
    assert all(s.get("reason") for s in skipped), "a skip must say why"
