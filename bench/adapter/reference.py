"""A plain, deterministic implementation of MODEL.md.

The null adapter proves the measures can be failed. This one proves they can
be passed — without a model, a database, or anything clever. It is the second
half of the control: a benchmark whose measures nothing satisfies is as
useless as one everything satisfies.

It is not a product and not anyone's architecture. It is MODEL.md written out
in about two hundred lines: entitlement by group, rules that bind downward,
announcements that travel one hop, contradictions resolved by recency,
retraction delivered as an event to everyone the claim reached, and a bounded
read that drops notes before rules and says how many it dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bench.adapter.protocol import (
    Agent,
    Declarations,
    Info,
    Kind,
    Read,
    Receipt,
    Shown,
    World,
    Write,
)


@dataclass
class _Item:
    id: str
    group: str
    content: str
    kind: Kind
    subject: str | None
    by_owner: bool
    seq: int
    announced: bool = False
    retracted: bool = False
    replaced: bool = False
    relayed_by: set[str] = field(default_factory=set)


class ReferenceMemory:
    """Governed shared memory, implemented directly from the model."""

    name = "reference"

    def __init__(self) -> None:
        self._reset(World(groups=()))

    def _reset(self, world: World) -> None:
        self.world_ = world
        self.items: dict[str, _Item] = {}
        self.seq = 0
        self.containers: dict[str, str] = {inner: outer for inner, outer in world.part_of}
        self.listens: dict[str, set[str]] = {}
        for group, source in world.listens_to:
            self.listens.setdefault(group, set()).add(source)
        self.parts: dict[str, set[str]] = {}
        for inner, outer in world.part_of:
            self.parts.setdefault(outer, set()).add(inner)
        self.bound = world.bound
        self.delivered: dict[str, set[str]] = {}      # item id -> groups shown it
        self.pending: dict[str, list[str]] = {}       # group -> item ids to announce as gone

    # --- API --------------------------------------------------------------

    def info(self) -> Info:
        return Info(
            id="reference",
            name="reference (MODEL.md, implemented plainly)",
            version="0.1.0",
            declarations=Declarations(
                notes_flow_down=False,
                listening_is_transitive=False,
                multiple_containers=False,
            ),
        )

    def world(self, world: World) -> None:
        self._reset(world)

    def write(self, agent: Agent, write: Write) -> Receipt:
        self.seq += 1
        item = _Item(
            id=f"i{self.seq}",
            group=agent.group,
            content=write.content,
            kind=write.kind,
            subject=write.subject,
            by_owner=agent.owner,
            seq=self.seq,
        )
        if write.replaces and write.replaces in self.items:
            self.items[write.replaces].replaced = True
        # Recency within a group settles a contradiction on one subject, and
        # an identical restatement is not a second item.
        for other in self.items.values():
            if other.group != item.group or other.retracted or other.replaced:
                continue
            if other.by_owner and not item.by_owner:
                continue   # the fleet does not supersede its owner by writing later
            same_subject = item.subject is not None and other.subject == item.subject
            same_text = other.content.strip() == item.content.strip()
            if (same_subject and other.kind == item.kind) or same_text:
                other.replaced = True
        self.items[item.id] = item
        return Receipt(id=item.id, accepted=True)

    def announce(self, agent: Agent, receipt_id: str) -> Receipt:
        item = self.items.get(receipt_id)
        if item is None or item.retracted or item.replaced:
            return Receipt(id=receipt_id, accepted=False,
                           reason="not held: unknown, retracted or replaced")
        if item.group == agent.group:
            item.announced = True
        elif agent.group in self.delivered.get(item.id, set()):
            item.relayed_by.add(agent.group)   # passing on what you were shown
        else:
            return Receipt(id=receipt_id, accepted=False, reason="not yours to announce")
        return Receipt(id=item.id, accepted=True)

    def retract(self, agent: Agent, receipt_id: str) -> Receipt:
        item = self.items.get(receipt_id)
        if item is None:
            return Receipt(id=receipt_id, accepted=False, reason="unknown")
        if item.group != agent.group and not agent.owner:
            return Receipt(id=receipt_id, accepted=False, reason="not yours to retract")
        item.retracted = True
        # Everyone the claim reached is owed notice, including through relays.
        for group in self.delivered.get(item.id, set()):
            self.pending.setdefault(group, []).append(item.id)
        return Receipt(id=item.id, accepted=True)

    def read(self, agent: Agent) -> Read:
        shown = self._visible(agent.group)
        shown, dropped = self._bound(shown)
        items = [self._render(item, agent.group) for item in shown]
        for item_id in self.pending.pop(agent.group, []):
            item = self.items[item_id]
            items.append(Shown(
                content=item.content, kind=item.kind, origin=item.group,
                binding=False, receipt=item.id, event="withdrawn",
            ))
        for item in shown:
            self.delivered.setdefault(item.id, set()).add(agent.group)
        return Read(
            items=tuple(items),
            words=sum(len(i.content.split()) for i in items),
            dropped=dropped,
        )

    def settle(self) -> None:
        return None

    # --- entitlement ------------------------------------------------------

    def _ancestors(self, group: str) -> list[str]:
        out, seen = [], {group}
        cur = self.containers.get(group)
        while cur and cur not in seen:
            out.append(cur)
            seen.add(cur)
            cur = self.containers.get(cur)
        return out

    def _visible(self, group: str) -> list[_Item]:
        ancestors = self._ancestors(group)
        heard_from = self.listens.get(group, set())
        container = self.containers.get(group)
        out: list[_Item] = []
        for item in self.items.values():
            if item.retracted or item.replaced:
                continue
            if item.group == group:
                out.append(item)                                  # own memory
            elif item.kind == "rule" and item.group in ancestors:
                out.append(item)                                  # rules bind downward
            elif item.announced and (item.group in heard_from
                                     or item.group == container):
                out.append(item)                                  # heard directly
            elif item.relayed_by & (heard_from | ({container} if container else set())):
                out.append(item)                                  # heard second-hand
        out = [i for i in out if not self._outranked(i, group)]
        return sorted(out, key=lambda i: i.seq)

    def _outranked(self, item: _Item, group: str) -> bool:
        """An owner rule on a subject outranks the fleet's own rule on it."""
        if item.kind != "rule" or item.by_owner or item.subject is None:
            return False
        covering = {group, *self._ancestors(group)}
        return any(
            other.by_owner and other.kind == "rule" and other.subject == item.subject
            and other.group in covering and not (other.retracted or other.replaced)
            for other in self.items.values()
        )

    def _binding(self, item: _Item, group: str) -> bool:
        if item.kind != "rule":
            return False
        return item.group == group or item.group in self._ancestors(group)

    def _render(self, item: _Item, group: str) -> Shown:
        via = None
        if item.group != group and item.relayed_by:
            heard_from = self.listens.get(group, set()) | {self.containers.get(group)}
            relays = sorted(item.relayed_by & {g for g in heard_from if g})
            direct = item.announced and (item.group in (self.listens.get(group, set())
                                                        | {self.containers.get(group)}))
            if relays and not direct:
                via = relays[0]
        return Shown(
            content=item.content,
            kind=item.kind,
            origin=item.group,
            binding=self._binding(item, group),
            via=via,
            receipt=item.id,
        )

    # --- staying within the bound ----------------------------------------

    def _bound(self, items: list[_Item]) -> tuple[list[_Item], int]:
        """Drop the oldest notes until the read fits. Rules are never dropped:
        an agent bound by a rule it cannot see cannot comply."""
        def words(rows: list[_Item]) -> int:
            return sum(len(i.content.split()) for i in rows)

        kept = list(items)
        dropped = 0
        while words(kept) > self.bound:
            notes = [i for i in kept if i.kind == "note"]
            if not notes:
                break            # only rules left; never drop one to fit
            kept.remove(notes[0])
            dropped += 1
        return kept, dropped
