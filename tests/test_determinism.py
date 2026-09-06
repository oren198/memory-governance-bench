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


def _template_patterns():
    import re
    from bench.canary import _NOTE_TAILS, _OBSERVED, _RULE_TAILS, _RULES, _SUBJECTS

    pats = []
    for tpl in _RULES + _OBSERVED:
        pat = re.escape(tpl)
        for ph in ("\\{s\\}", "\\{v\\}", "\\{w\\}", "\\{d\\}"):
            pat = pat.replace(ph, ".+")
        pats.append(re.compile(pat + r"\.$"))
    for tail in _RULE_TAILS + _NOTE_TAILS:
        pats.append(re.compile(re.escape(tail) + r"\.$"))
    return pats


def _clauses(text, tok):
    assert text.startswith(f"{tok}: ")
    rest = text[len(tok) + 2:]
    parts = [c.strip() for c in rest.split(". ") if c.strip()]
    return [c if c.endswith(".") else c + "." for c in parts]


def test_planted_text_is_a_statement_not_word_salad():
    """A system may decline text that means nothing. If the benchmark plants
    word salad, such a system fails every measure downstream of a write for a
    reason that has nothing to do with governance."""
    pats = _template_patterns()
    for kind, words in (("rule", 20), ("note", 12), ("note", 30)):
        text = sentence(7, "A1", 0, "rule", words, kind)
        for clause in _clauses(text, canary(7, "A1", 0, "rule")):
            assert any(p.match(clause) for p in pats), clause
        assert len(text.split()) >= words


def test_two_planted_items_are_two_different_claims():
    """A system that treats a near-identical restatement as a duplicate rather
    than as new evidence is behaving well. Found by the architect: two notes
    shared one template with only the subject swapped, and the second was
    declined as a restatement of the first."""
    # 60 is the largest flood any scenario plants (family G).
    texts = [sentence(11, "G1", 0, f"n{i}", 12, "note", i) for i in range(60)]
    bodies = [t.split(": ", 1)[1] for t in texts]
    assert len(set(bodies)) == len(bodies)
    shapes = set()
    for body in bodies:
        # same frame and same subject would make two items one claim restated
        shape = tuple(w for w in body.split() if not w.strip(",.").isdigit())
        assert shape not in shapes, body
        shapes.add(shape)


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
    from bench.canary import _NOTE_TAILS, _OBSERVED, _RULE_TAILS, _RULES

    markers = (
        "agreed", "approved", "signed off", "ratified", "consensus",
        "objected", "everyone", "we all", "as decided", "per the",
        "recorded in", "documented in", "see the", "details are in",
    )
    for text in _RULES + _OBSERVED + _RULE_TAILS + _NOTE_TAILS:
        low = text.lower()
        hits = [m for m in markers if m in low]
        assert not hits, f"{text!r} asserts social proof: {hits}"


def test_no_clause_is_repeated_to_reach_the_word_floor():
    """Verbatim repetition reads as noise, and a system that declines noise is
    right to. Found by the architect: a rule met its floor by appending the
    same trailer twice. The floor yields; the text never repeats itself."""
    for kind in ("rule", "note"):
        for ordinal in range(12):
            text = sentence(5, "A1", 1, f"t{ordinal}", 200, kind, ordinal)
            clauses = [c.strip() for c in text.split(". ") if c.strip()]
            assert len(set(clauses)) == len(clauses), text
