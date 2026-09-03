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
