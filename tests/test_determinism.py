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


def test_planted_text_is_a_statement_not_word_salad():
    """A system may decline text that means nothing. If the benchmark plants
    word salad, such a system fails every measure downstream of a write for a
    reason that has nothing to do with governance."""
    from bench.canary import _NOTE_TAILS, _NOTES, _RULE_TAILS, _RULES, _SUBJECTS

    known = {t.format(s=s) + "." for s in _SUBJECTS for t in _RULES + _NOTES}
    known |= {t + "." for t in _RULE_TAILS + _NOTE_TAILS}
    for kind, words in (("rule", 20), ("note", 12), ("note", 30)):
        text = sentence(7, "A1", 0, "rule", words, kind)
        tok = canary(7, "A1", 0, "rule")
        assert text.startswith(f"{tok}: ")
        rest = text[len(tok) + 2:]
        parts = [p.strip() + "." for p in rest.split(". ")]
        parts[-1] = parts[-1].rstrip(".") + "."
        assert all(p in known for p in parts), parts
        assert len(text.split()) >= words


def test_a_rule_reads_as_an_instruction():
    from bench.canary import _RULES, _SUBJECTS

    instructions = {t.format(s=s) for s in _SUBJECTS for t in _RULES}
    text = sentence(3, "A1", 1, "rule", 12, "rule")
    body = text.split(": ", 1)[1].split(". ")[0].rstrip(".")
    assert body in instructions


def test_planted_text_never_asserts_that_anyone_agreed_to_it():
    """A system may decline an item that claims a ratification it cannot show,
    and guarding against that is good governance. Filler asserting social
    proof would fail such a system for a reason that is not about governance.
    Found by the architect: an earlier bank said "this was agreed with the
    owning team"."""
    from bench.canary import _NOTE_TAILS, _NOTES, _RULE_TAILS, _RULES

    markers = (
        "agreed", "approved", "signed off", "ratified", "consensus",
        "objected", "everyone", "we all", "as decided", "per the",
        "recorded in", "documented in", "see the", "details are in",
    )
    for text in _RULES + _NOTES + _RULE_TAILS + _NOTE_TAILS:
        low = text.lower()
        hits = [m for m in markers if m in low]
        assert not hits, f"{text!r} asserts social proof: {hits}"
