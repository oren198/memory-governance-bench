"""Documentation is part of the contract, so drift between it and the code
is a test failure rather than something a reader discovers later."""

import ast
import re
from pathlib import Path

from bench.scenario import registry

ROOT = Path(__file__).resolve().parent.parent
MEASURES = (ROOT / "MEASURES.md").read_text()
MODEL = (ROOT / "MODEL.md").read_text()

# Words belonging to one implementation's design, which must never appear in
# the benchmark's own vocabulary (see MEMORY/CHARTER: the model is general).
FORBIDDEN = (
    "scope", "stratum", "strata", "judge", "publication", "perspective",
    "directive", "summary",
)
EXEMPT_PATHS = {"adapters"}   # adapter notes may name the system they adapt


def _documented() -> set[str]:
    return set(re.findall(r"^\*\*([A-Z][0-9]+[a-z]?) ", MEASURES, re.M))


def test_every_measure_is_documented():
    missing = sorted(set(registry()) - _documented())
    assert not missing, f"measures with no entry in MEASURES.md: {missing}"


def test_every_documented_measure_exists():
    extra = sorted(_documented() - set(registry()))
    assert not extra, f"documented but never run: {extra}"


def test_families_agree_with_the_charter():
    charter = (ROOT / "CHARTER.md").read_text()
    families = {family for family, _doc, _fn in registry().values()}
    for family in families:
        assert re.search(rf"\*\*{family} —", charter) or family == "P", (
            f"family {family} is not described in CHARTER.md"
        )


def _prose(path: Path) -> str:
    """Prose only: no fenced blocks, no inline code, no CSS or identifiers.
    A path like `adapters/strata/` is a reference, not vocabulary."""
    text = path.read_text()
    if path.suffix == ".md":
        text = re.sub(r"```.*?```", " ", text, flags=re.S)
        text = re.sub(r"`[^`]*`", " ", text)
        return text.lower()
    tree = ast.parse(text)
    docs = [ast.get_docstring(tree) or ""]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            docs.append(ast.get_docstring(node) or "")
    comments = re.findall(r"#(.*)$", text, re.M)
    return " ".join(docs + comments).lower()


def test_no_implementation_vocabulary_in_the_benchmark():
    """The model must be readable by a team with a completely different
    design; borrowed vocabulary is how a benchmark quietly becomes a
    conformance suite for one engine. Checked against prose, since a path or
    an HTML tag named `summary` is a reference, not a concept."""
    offenders = []
    for path in list(ROOT.glob("*.md")) + list((ROOT / "bench").rglob("*.py")):
        if any(part in EXEMPT_PATHS for part in path.parts):
            continue
        if path.name in {"README.md", "CHARTER.md"}:
            continue   # these name the reference implementation on purpose
        text = _prose(path)
        for word in FORBIDDEN:
            if re.search(rf"\b{word}\b", text):
                offenders.append(f"{path.relative_to(ROOT)}: {word}")
    assert not offenders, f"implementation vocabulary leaked: {offenders}"


def test_model_defines_every_term_the_measures_use():
    for term in ("group", "note", "rule", "announce", "retract",
                 "owner", "part of", "listens to", "legitimate"):
        assert term in MODEL.lower(), f"MODEL.md does not define {term!r}"


def test_charter_and_model_agree_that_a_choice_is_not_an_exemption():
    """A system that declares a wider policy conforms on P but still owes
    every forced rule — stated because the graders enforce it either way, and
    an outside team must not have to discover it from a failing run."""
    charter = (ROOT / "CHARTER.md").read_text().lower()
    assert "does not exempt" in charter
    assert "never excuses a forced obligation" in MODEL.lower()
    assert "never a defence against a forced rule" in MEASURES.lower()
