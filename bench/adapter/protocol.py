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
    bound:        the maximum size of any one read, in words. The benchmark
                  counts what it was shown; this tells the system the target.
    """

    groups: tuple[str, ...]
    part_of: tuple[tuple[str, str], ...] = ()
    listens_to: tuple[tuple[str, str], ...] = ()
    owner_groups: tuple[str, ...] = ()
    bound: int = 500


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
    """What a reader is shown.

    items:   everything shown, in the system's own order.
    words:   the system's own count, recorded for cost reporting. Never used
             for scoring — the benchmark counts what it was shown.
    dropped: how many items the system condensed away rather than showing.
             ``None`` means the system does not report it, which family G
             reads as "the reader was not told". Zero is a positive claim
             that nothing was dropped.
    """

    items: tuple[Shown, ...]
    words: int = 0
    dropped: int | None = None


class Unsupported(Exception):
    """Raised for an operation the system has no equivalent of. Reported as
    `unsupported` — scored as failure, labelled distinctly."""


@dataclass(frozen=True)
class Declarations:
    """A system's position on the rules the promise does not force
    (MODEL.md § "Forced by the promise, and chosen"). Family P grades the
    system against these and nothing else; missing keys default to False."""

    notes_flow_down: bool = False
    listening_is_transitive: bool = False
    multiple_containers: bool = False


@dataclass(frozen=True)
class Info:
    id: str
    name: str
    version: str
    declarations: Declarations = Declarations()


class MemorySystem(Protocol):
    name: str

    def info(self) -> Info:
        """Identity and declared policy. Read once, before any world is built."""
        ...

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
