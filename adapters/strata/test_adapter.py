"""Adapter tests — the protocol, driven directly, with the mechanical judge.

These are not benchmark scenarios; they are the shapes the benchmark's
scenarios reduce to, asserted against the adapter itself so a break is
localised before a run of 200 scenarios has to point at it. Only the stub
judge configuration is exercised: a test that needed a model call would be a
test of the model.

Each test names the scenario it stands in for.
"""

from __future__ import annotations

import pytest

from adapters.strata.adapter import StrataStubJudgeMemory
from bench.adapter.protocol import Agent, World, Write


@pytest.fixture()
def memory(tmp_path):
    system = StrataStubJudgeMemory(workdir=str(tmp_path))
    yield system
    system._teardown()


def _standard(memory) -> dict[str, str]:
    """MODEL.md's worked example: Company ⊃ {Sales, Support ⊃ Tier-2, Billing},
    Support listens to Billing."""
    g = {
        "company": "company",
        "support": "support",
        "tier2": "tier2",
        "billing": "billing",
    }
    memory.world(
        World(
            groups=tuple(g.values()),
            part_of=(
                (g["support"], g["company"]),
                (g["billing"], g["company"]),
                (g["tier2"], g["support"]),
            ),
            listens_to=((g["support"], g["billing"]),),
            bound=400,
        )
    )
    return g


def _agent(group: str) -> Agent:
    return Agent(id=f"a@{group}", group=group)


def _contents(read) -> list[str]:
    return [i.content for i in read.items if i.event is None]


def _shows(read, token: str) -> bool:
    return any(token in i.content for i in read.items if i.event is None)


# --- F0 -------------------------------------------------------------------


def test_retracting_an_unannounced_note_removes_it(memory):
    """F0 (first half). A note that was never announced is retractable: the
    retraction is an ordinary contribution superseding it, not Unsupported."""
    g = _standard(memory)
    a = _agent(g["support"])
    receipt = memory.write(a, Write(content="CANARY-F0 the refund API times out", kind="note"))
    assert receipt.accepted
    memory.read(a)

    result = memory.retract(a, receipt.id)

    assert result.accepted, result.reason
    read = memory.read(a)
    assert not _shows(read, "CANARY-F0"), _contents(read)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Strata #197: a scope is never told about its OWN retraction. ADR 0014 D1 "
        "— a scope's own contribution is not a trigger — and affected_scopes "
        "excludes the source scope for every publication change, so no change "
        "event reaches the retracting group and read() has no engine-produced "
        "notice to render. The adapter does not fabricate one."
    ),
)
def test_retracting_an_unannounced_note_tells_the_group(memory):
    """F0 (second half). MODEL.md: the readers the claim reached are owed
    notice, and the writer's own group is among them."""
    g = _standard(memory)
    a = _agent(g["support"])
    receipt = memory.write(a, Write(content="CANARY-F0b the refund API times out", kind="note"))
    memory.read(a)
    memory.retract(a, receipt.id)

    read = memory.read(a)
    assert [i for i in read.items if i.event == "withdrawn" and "CANARY-F0b" in i.content]


# --- S4b ------------------------------------------------------------------


def test_withdrawing_an_announcement_tells_the_listener(memory):
    """S4b. Billing announces, Support is shown it, Billing retracts: Support's
    next read carries the withdrawal event, not merely an absence."""
    g = _standard(memory)
    billing, support = _agent(g["billing"]), _agent(g["support"])
    receipt = memory.write(billing, Write(content="CANARY-S4 the batch limit is 200", kind="note"))
    assert memory.announce(billing, receipt.id).accepted
    assert _shows(memory.read(support), "CANARY-S4")

    assert memory.retract(billing, receipt.id).accepted

    read = memory.read(support)
    assert not _shows(read, "CANARY-S4"), _contents(read)
    events = [i for i in read.items if i.event == "withdrawn" and "CANARY-S4" in i.content]
    assert events, read.items
    assert events[0].origin == g["billing"]


# --- S6 -------------------------------------------------------------------


def test_relayed_announcement_carries_origin_and_via(memory):
    """S6. Billing announces; Support re-announces the receipt it was SHOWN;
    Tier-2 (part of Support) is shown it with origin Billing, via Support."""
    g = _standard(memory)
    billing, support, tier2 = _agent(g["billing"]), _agent(g["support"]), _agent(g["tier2"])
    receipt = memory.write(billing, Write(content="CANARY-S6 refunds need a signature", kind="note"))
    assert memory.announce(billing, receipt.id).accepted

    heard = [i for i in memory.read(support).items if "CANARY-S6" in i.content and i.event is None]
    assert heard and heard[0].receipt, "Support was not shown a relayable receipt"

    relayed = memory.announce(support, heard[0].receipt)
    assert relayed.accepted, relayed.reason

    shown = [i for i in memory.read(tier2).items if "CANARY-S6" in i.content and i.event is None]
    assert shown, "Tier-2 was shown nothing"
    assert [i.origin for i in shown] == [g["billing"]]
    assert [i.via for i in shown] == [g["support"]]


# --- T2 -------------------------------------------------------------------


def test_a_replacement_replaces(memory):
    """T2. A write that replaces an earlier one: the old leaves, the new stays."""
    g = _standard(memory)
    a = _agent(g["billing"])
    first = memory.write(a, Write(content="CANARY-OLD the batch limit is 100", kind="note",
                                  subject="batch"))
    memory.write(a, Write(content="CANARY-NEW the batch limit is 200", kind="note",
                          subject="batch", replaces=first.id))

    read = memory.read(a)
    assert not _shows(read, "CANARY-OLD"), _contents(read)
    assert _shows(read, "CANARY-NEW"), _contents(read)


def test_a_replaced_rule_leaves(memory):
    """T2/F1 for the binding kind: a superseded directive is not still shown."""
    g = _standard(memory)
    a = _agent(g["billing"])
    first = memory.write(a, Write(content="CANARY-R1 answer within four hours", kind="rule",
                                  subject="sla"))
    memory.write(a, Write(content="CANARY-R2 answer within two hours", kind="rule",
                          subject="sla", replaces=first.id))

    read = memory.read(a)
    assert not _shows(read, "CANARY-R1"), _contents(read)
    assert _shows(read, "CANARY-R2"), _contents(read)


# --- drain on read --------------------------------------------------------


def test_read_drains_pending_input_changes(memory):
    """ADR 0014 D6. A parent announces AFTER the child's first read; the child's
    next read shows the item, and the record holds a JUDGED manager-refresh row.

    The second assertion is the one that matters: composition would show the
    parent's publication whether or not a refresh ever ran, so "the item is
    shown" is not evidence that the drain happened. A verdict against the
    change notice is.
    """
    g = _standard(memory)
    support, tier2 = _agent(g["support"]), _agent(g["tier2"])
    memory.read(tier2)

    receipt = memory.write(support, Write(content="CANARY-D1 escalate over $500", kind="note"))
    assert memory.announce(support, receipt.id).accepted

    events = memory._record.list_change_events(scope_id=g["tier2"], unprocessed_only=True)
    assert events, "the announcement wrote no change event for the child"

    read = memory.read(tier2)
    assert _shows(read, "CANARY-D1"), _contents(read)

    notices = [
        memory._record.get_contribution(e.contribution_id)
        for e in memory._record.list_change_events(scope_id=g["tier2"])
    ]
    assert any(n.subject == "manager-refresh" for n in notices), notices
    judged = [
        n for n in notices
        if n.subject == "manager-refresh" and memory._record.get_judgment(n.id) is not None
    ]
    assert judged, "the drain ran no judgment against the change notice"
    assert not memory._record.list_change_events(scope_id=g["tier2"], unprocessed_only=True)
