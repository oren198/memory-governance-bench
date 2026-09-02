"""The whole surface a system under test exposes to the benchmark.

Everything the benchmark knows about a system passes through this file.
Nothing here names a mechanism: no judge, no summary, no prompt, no store.
A system is a black box that agents write to, share from, retract from, and
read from; the benchmark scores only what `read` returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

Kind = Literal["observation", "decision"]


@dataclass(frozen=True)
class World:
    """The topology a scenario runs in.

    scopes:    every scope id.
    contains:  (outer, inner) pairs — `outer` contains `inner`; decisions of
               `outer` bind readers of `inner`.
    refers:    (scope, peer) pairs — `scope` wants to hear what `peer` shares.
               May form cycles.
    operator:  scopes the operator may make decisions for, or None.
    """

    scopes: tuple[str, ...]
    contains: tuple[tuple[str, str], ...] = ()
    refers: tuple[tuple[str, str], ...] = ()
    operator: tuple[str, ...] = ()


@dataclass(frozen=True)
class Actor:
    """Who is acting. `scope` is where they act from."""

    id: str
    scope: str
    is_operator: bool = False


@dataclass(frozen=True)
class Write:
    content: str
    kind: Kind
    supersedes: str | None = None  # receipt id of the item this replaces, if any
    subject: str | None = None      # optional topic tag; systems may ignore it


@dataclass(frozen=True)
class Receipt:
    """What the system hands back for a write or share. `id` must be stable
    enough to be used in later `retract`/`supersedes` calls."""

    id: str
    accepted: bool
    reason: str | None = None


@dataclass(frozen=True)
class Shown:
    """One item a reader is shown. This is the unit every measure grades.

    content:     the text as shown.
    kind:        observation or decision, *as shown* — the label a reader sees.
    origin:      the scope the system says this came from.
    via:         if the item reached the reader through another scope (a
                 relay), that scope; else None.
    attributed:  if the item is a restatement of another scope's claim, the
                 scope it is attributed to; else None.
    binding:     whether the reader is told this binds them.
    receipt:     the receipt id of the write/share it derives from, when the
                 system can say; else None.
    event:       None for ordinary items; "withdrawn" for an item the reader
                 is told was retracted (delivered as an event, not silence).
    """

    content: str
    kind: Kind
    origin: str
    binding: bool
    via: str | None = None
    attributed: str | None = None
    receipt: str | None = None
    event: Literal["withdrawn"] | None = None


@dataclass(frozen=True)
class ReadResult:
    items: tuple[Shown, ...]
    words: int = field(default=0)  # size of the read surface, for family G


class Unsupported(Exception):
    """Raised by an adapter for an operation the system has no equivalent of.
    Reported as `unsupported` — scored as failure, labelled distinctly."""


class MemorySystem(Protocol):
    """Implement this to put a system under test."""

    name: str

    def setup(self, world: World) -> None: ...

    def write(self, actor: Actor, write: Write) -> Receipt: ...

    def retract(self, actor: Actor, receipt_id: str) -> Receipt: ...

    def share(self, actor: Actor, receipt_id: str) -> Receipt:
        """Offer a held item to the scopes that refer to the actor's scope
        or are contained by it."""
        ...

    def unshare(self, actor: Actor, receipt_id: str) -> Receipt: ...

    def read(self, actor: Actor) -> ReadResult:
        """Everything the actor is shown when acting from their scope."""
        ...

    def settle(self) -> None:
        """Finish any deferred work between a write and the next read.
        A system with no deferred work returns immediately."""
        ...

    def teardown(self) -> None: ...
