"""The null adapter: append everything, show everyone, forget nothing.

This is not a strawman for its own sake. It is the control: a memory with no
governance at all, which must score ~1.0 on contribution and fail every
failure-mode family. If any family passes it, that family's graders do not
bite and they are wrong.

It is deliberately naive rather than deliberately broken — it implements
every operation (so failures are behavioural, never `unsupported`), tells
the truth about where items were written, and simply has no notion of
entitlement, authority, contradiction, retraction or bound.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    content: str
    kind: Kind
    group: str


class NullMemory:
    """Shared memory with no governance."""

    name = "null"

    def __init__(self) -> None:
        self._items: list[_Item] = []
        self._n = 0

    def info(self) -> Info:
        return Info(
            id="null",
            name="null (append-everything baseline)",
            version="0.1.0",
            declarations=Declarations(),
        )

    def world(self, world: World) -> None:
        self._items = []
        self._n = 0

    def write(self, agent: Agent, write: Write) -> Receipt:
        self._n += 1
        rid = f"i{self._n}"
        # No supersession: `replaces` is accepted and ignored, which is the
        # whole point of the baseline.
        self._items.append(
            _Item(id=rid, content=write.content, kind=write.kind, group=agent.group)
        )
        return Receipt(id=rid, accepted=True)

    def announce(self, agent: Agent, receipt_id: str) -> Receipt:
        # Everything is already shown to everyone; announcing changes nothing.
        return Receipt(id=receipt_id, accepted=True)

    def retract(self, agent: Agent, receipt_id: str) -> Receipt:
        # Accepted and ignored: memory that only accumulates.
        return Receipt(id=receipt_id, accepted=True)

    def read(self, agent: Agent) -> Read:
        items = tuple(
            Shown(
                content=it.content,
                kind=it.kind,
                origin=it.group,
                binding=(it.kind == "rule"),
                receipt=it.id,
            )
            for it in self._items
        )
        return Read(items=items, words=sum(len(i.content.split()) for i in items))

    def settle(self) -> None:
        return None
