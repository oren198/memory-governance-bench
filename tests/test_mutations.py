"""Mutation tests: break one rule, and check the right family notices.

The two baselines show the measures can be failed and passed. These show they
are wired to the failures they claim to catch — a family that stays at 1.0
while the behaviour it names is broken is measuring something else.

Each mutant is the reference implementation with exactly one rule removed.
"""

import pytest

from bench.adapter.protocol import Receipt, Shown
from bench.adapter.reference import ReferenceMemory, _Item
from bench.runner import run


class NoNotice(ReferenceMemory):
    """Retraction removes the claim but tells nobody."""

    def read(self, agent):
        self.pending.pop(agent.group, None)
        return super().read(agent)


class KeepBothSides(ReferenceMemory):
    """Never resolve a contradiction: every write stands."""

    def write(self, agent, w):
        self.seq += 1
        item = _Item(id=f"i{self.seq}", group=agent.group, content=w.content,
                     kind=w.kind, subject=w.subject, by_owner=agent.owner, seq=self.seq)
        self.items[item.id] = item
        return Receipt(id=item.id, accepted=True)


class Unbounded(ReferenceMemory):
    """Ignore the bound entirely."""

    def _bound(self, items):
        return items, 0


class ForgetRules(ReferenceMemory):
    """Trim to the bound by dropping whatever is oldest, rules included."""

    def _bound(self, items):
        kept, dropped = list(items), 0
        while sum(len(i.content.split()) for i in kept) > self.bound and kept:
            kept.pop(0)
            dropped += 1
        return kept, dropped


class FalseOrigin(ReferenceMemory):
    """Claim every item was written where the reader is."""

    def _render(self, item, group):
        s = super()._render(item, group)
        return Shown(content=s.content, kind=s.kind, origin=group, binding=s.binding,
                     via=s.via, attributed_to=s.attributed_to, receipt=s.receipt,
                     event=s.event)


class NotesBind(ReferenceMemory):
    """Show everything as binding on the reader."""

    def _binding(self, item, group):
        return True


class LeakDownUndeclared(ReferenceMemory):
    """Pass a container's notes to its parts while declaring it does not."""

    def _visible(self, group):
        out = super()._visible(group)
        ancestors = set(self._ancestors(group))
        extra = [i for i in self.items.values()
                 if i.group in ancestors and i.kind == "note"
                 and not (i.retracted or i.replaced)]
        return sorted(out + extra, key=lambda i: i.seq)


@pytest.mark.parametrize(
    "mutant, family, what",
    [
        (NoNotice, "S", "a retraction that removes without telling anyone"),
        (KeepBothSides, "T", "holding both sides of a contradiction"),
        (Unbounded, "G", "a read that grows without limit"),
        (ForgetRules, "G", "dropping a binding rule to stay within the bound"),
        (FalseOrigin, "A", "claiming an item came from somewhere it did not"),
        (NotesBind, "A", "showing an observation as though it binds"),
    ],
)
def test_family_catches_its_own_failure(mutant, family, what):
    result = run(mutant())
    assert result.families[family]["rate"] < 1.0, (
        f"family {family} did not notice {what}"
    )


def test_reference_passes_all_of_them():
    """The mutants differ from the reference in exactly one behaviour, so the
    unmutated original must pass everything the mutants fail."""
    assert run(ReferenceMemory()).headline == {"governance": 1.0, "contribution": 1.0}


def test_policy_catches_an_undeclared_choice():
    """A declaration is scoring input the participant controls, so it is
    checked against behaviour: declaring one thing and doing another fails."""
    assert run(LeakDownUndeclared()).policy["rate"] < 1.0
    assert run(ReferenceMemory()).policy["rate"] == 1.0


def test_mutants_keep_contributing():
    """Every mutant still shows legitimate items, so a governance drop cannot
    be explained away as the system having simply stopped remembering."""
    for mutant in (NoNotice, FalseOrigin, NotesBind, Unbounded):
        assert run(mutant()).families["R"]["rate"] == 1.0, mutant.__name__


class NotesRefused(ReferenceMemory):
    """Holds rules, refuses notes. A memory that keeps only decisions.

    Not an absurd system — a real judge declined an observation for having
    "no directive weight of its own". But a fleet memory that holds only
    decisions cannot carry what one agent learned to the agent who needs it,
    which is half the promise; and every measure that says "a note must not
    do X" is satisfied for free.
    """

    def write(self, agent, w):
        if w.kind != "rule":
            self.seq += 1
            return Receipt(id=f"i{self.seq}", accepted=True)
        return super().write(agent, w)


class AdmitsNothing(ReferenceMemory):
    """Accepts every write, holds none of it. Shows only what it must not.

    Not a plausible system — a deliberate adversary against the shape of a
    measure rather than against a rule. Every containment, forgetting and
    announcement measure asks whether some reader was NOT shown an item, and
    a system holding nothing satisfies all of them for free. Found by the
    architect: a real system's admission step declined several plants, and
    family C scored 20/20 because the absence held vacuously.
    """

    def write(self, agent, w):
        self.seq += 1
        return Receipt(id=f"i{self.seq}", accepted=True)


@pytest.mark.parametrize("family", ["C", "S", "F", "T", "E", "G", "A", "R"])
def test_a_system_that_holds_nothing_passes_no_absence(family):
    """An absence must be earned: the plant is shown to a reader entitled to
    it first, so declining the write fails the precondition instead of
    passing the measure."""
    result = run(AdmitsNothing())
    assert result.families[family]["rate"] < 1.0, (
        f"family {family} passes vacuously for a system that admits nothing"
    )


@pytest.mark.parametrize("family", ["A", "R"])
def test_refusing_notes_is_not_governance(family):
    """Keeping only decisions is not the same as governing memory well: the
    measures that say what a note may not do must not be satisfied by a
    system that has no notes."""
    assert run(NotesRefused()).families[family]["rate"] < 1.0


def test_holding_nothing_is_not_governance():
    """The headline must not reward it either."""
    assert run(AdmitsNothing()).headline["governance"] == 0.0
