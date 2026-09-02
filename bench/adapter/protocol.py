"""The whole surface a system under test exposes to the benchmark.

Vocabulary and meaning: MODEL.md. Canonical contract: SPEC.md §2 (HTTP);
this is its Python form. Nothing here names a mechanism. The benchmark
scores only what `read` returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

Kind = Literal["note", "rule"]


@dataclass(frozen=True)
class World:
    """The fleet a scenario runs in.

    groups:       every group id.
    part_of:      (group, container) pairs — the container's rules bind the group.
    listens_to:   (group, source) pairs — the source's announcements are shown
                  to the group. Directed, one hop; may be mutual.
    owner_groups: groups the owner may write rules for.
    """

    groups: tuple[str, ...]
    part_of: tuple[tuple[str, str], ...] = ()
    listens_to: tuple[tuple[str, str], ...] = ()
    owner_groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class Agent:
    """Who is acting, and the group they act from."""

    id: str
    group: str
    owner: bool = False


@dataclass(frozen=True)
class Write:
    content: str
    kind: Kind
    replaces: str | None = None  # receipt id of the item this supersedes
    subject: str | None = None


@dataclass(frozen=True)
class Receipt:
    """Handed back for a write or announcement; `id` is used by later
    `retract` and `replaces`."""

    id: str
    accepted: bool
    reason: str | None = None


@dataclass(frozen=True)
class Shown:
    """One item a reader is shown — the unit every measure grades.
    Field meanings: MODEL.md § "What a reader is shown"."""

    content: str
    kind: Kind
    origin: str
    binding: bool
    via: str | None = None
    attributed_to: str | None = None
    receipt: str | None = None
    event: Literal["withdrawn"] | None = None


@dataclass(frozen=True)
class Read:
    items: tuple[Shown, ...]
    words: int = 0


class Unsupported(Exception):
    """Raised for an operation the system has no equivalent of. Reported as
    `unsupported` — scored as failure, labelled distinctly."""


class MemorySystem(Protocol):
    name: str

    def world(self, world: World) -> None:
        """Replace the fleet; wipe all memory."""
        ...

    def write(self, agent: Agent, write: Write) -> Receipt: ...

    def announce(self, agent: Agent, receipt_id: str) -> Receipt:
        """Offer a held item to the groups that listen to the agent's group
        and to the groups that are part of it."""
        ...

    def retract(self, agent: Agent, receipt_id: str) -> Receipt:
        """Take back a write or an announcement."""
        ...

    def read(self, agent: Agent) -> Read:
        """Everything the agent is shown, acting from its group."""
        ...

    def settle(self) -> None:
        """Finish deferred work; return when reads are stable. No-op for a
        system that decides synchronously."""
        ...
