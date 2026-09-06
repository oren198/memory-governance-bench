"""The scenario harness.

A measure is a function registered with :func:`scenario`. It receives a
:class:`Ctx`, builds a fleet, acts, reads, and records checks. The harness
owns every rule a scenario author would otherwise have to remember:

* ``settle()`` is called before every read and after every batch of writes,
  so no scenario can forget it;
* content is generated from the seed, so runs are reproducible;
* an :class:`Unsupported` operation aborts the scenario and marks it
  ``unsupported`` rather than silently passing;
* which group each canary was written in is tracked, so origin claims are
  checked against the truth rather than against the system's word.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Iterable

from bench.adapter.protocol import (
    Agent,
    Declarations,
    Kind,
    MemorySystem,
    Read,
    Receipt,
    Shown,
    Unsupported,
    World,
    Write,
)
from bench.canary import canary, sentence

VARIANTS = 5


@dataclass
class Check:
    id: str
    passed: bool
    detail: dict


@dataclass
class ScenarioResult:
    id: str
    measure: str
    family: str
    variant: int
    passed: bool | None      # None when the scenario was not applicable
    unsupported: bool
    skipped: bool = False
    checks: list[Check] = field(default_factory=list)
    error: str | None = None   # the scenario crashed — always a bug to fix
    reason: str | None = None  # why it was skipped or unsupported

    def to_json(self) -> dict:
        out = {
            "id": self.id,
            "measure": self.measure,
            "family": self.family,
            "variant": self.variant,
            "passed": self.passed,
            "unsupported": self.unsupported,
            "skipped": self.skipped,
            "checks": [{"id": c.id, "passed": c.passed, "detail": c.detail} for c in self.checks],
        }
        if self.error:
            out["error"] = self.error
        if self.reason:
            out["reason"] = self.reason
        return out


class Skip(Exception):
    """The scenario does not apply to this system's declared policy."""


class Timeout(Exception):
    """The scenario exceeded its wall-clock budget. A real system can hang or
    crawl; one slow scenario must not take the run down with it."""


class Ctx:
    """Everything a measure needs, and nothing a measure should reimplement."""

    def __init__(
        self,
        system: MemorySystem,
        scenario_id: str,
        variant: int,
        seed: int,
        declarations: Declarations,
        timeout: float | None = None,
    ) -> None:
        self.system = system
        self.scenario_id = scenario_id
        self.variant = variant
        self.seed = seed
        self.declarations = declarations
        self.checks: list[Check] = []
        self.calls = 0
        self._ordinals: dict[str, int] = {}
        self._roles: dict[str, str] = {}   # group id -> its role in the fleet
        self._deadline = (time.monotonic() + timeout) if timeout else None
        self._origin: dict[str, str] = {}   # canary -> group it was written in
        self._kind: dict[str, Kind] = {}    # canary -> kind it was written as
        self._settled = False

    def _tick(self, operation: str) -> None:
        """Checked on both sides of every call into the system: before, so a
        scenario that has already run out does not start more work, and after,
        so the call that spent the budget is the one blamed. A single call
        that never returns is the transport's problem, which is why the HTTP
        binding sets a socket timeout of its own."""
        self.calls += 1
        self._deadline_check(operation)

    def _deadline_check(self, operation: str) -> None:
        if self._deadline and time.monotonic() > self._deadline:
            raise Timeout(f"scenario budget exhausted at {operation}")

    # --- world ------------------------------------------------------------

    def build(
        self,
        groups: Iterable[str],
        part_of: Iterable[tuple[str, str]] = (),
        listens_to: Iterable[tuple[str, str]] = (),
        owner_groups: Iterable[str] = (),
        bound: int = 500,
        roles: dict[str, str] | None = None,
    ) -> None:
        # Roles belong to the fleet just built; a scenario that builds its own
        # gets the generic nouns unless it says which group plays which part.
        self._roles = dict(roles or {})
        self._tick("world")
        self.system.world(
            World(
                groups=tuple(groups),
                part_of=tuple(part_of),
                listens_to=tuple(listens_to),
                owner_groups=tuple(owner_groups),
                bound=bound,
            )
        )
        self._deadline_check("world")
        self._settled = False

    def gid(self, role: str) -> str:
        """A group name unique to this scenario and variant.

        `/world` is specified to wipe all memory, but a system that keys its
        storage on the group name and wipes imperfectly would carry one
        scenario's items into the next, and shared names make that invisible.
        Unique names make the contract impossible to half-keep.
        """
        return f"{role}_{self.scenario_id.lower()}_{self.variant}"

    def standard(self, bound: int = 500) -> dict[str, str]:
        """The fleet of MODEL.md's worked example, plus two groups the
        measures need: a group inside Billing, and a source Billing listens
        to. Names are suffixed per variant so no system can key on them."""
        g = {
            "company": self.gid("company"),
            "sales": self.gid("sales"),
            "support": self.gid("support"),
            "tier2": self.gid("tier2"),
            "billing": self.gid("billing"),
            "collections": self.gid("collections"),
            "finance": self.gid("finance"),
        }
        self.build(
            groups=g.values(),
            part_of=[
                (g["sales"], g["company"]),
                (g["support"], g["company"]),
                (g["billing"], g["company"]),
                (g["finance"], g["company"]),
                (g["tier2"], g["support"]),
                (g["collections"], g["billing"]),
            ],
            listens_to=[(g["support"], g["billing"]), (g["billing"], g["finance"])],
            owner_groups=[g["support"], g["company"]],
            bound=bound,
            roles={gid: role for role, gid in g.items()},
        )
        return g

    # --- acting -----------------------------------------------------------

    def agent(self, group: str, owner: bool = False) -> Agent:
        return Agent(id=f"{'owner' if owner else 'a'}@{group}", group=group, owner=owner)

    def canary(self, tag: str) -> str:
        return canary(self.seed, self.scenario_id, self.variant, tag)

    def _ordinal(self, tag: str) -> int:
        """This item's position among the distinct items the scenario plants.

        Two planted items must be two different claims: a system that reads
        its input may treat a near-identical restatement as a duplicate rather
        than as new evidence, and be right to."""
        return self._ordinals.setdefault(tag, len(self._ordinals))

    def text(self, tag: str, words: int = 12, kind: Kind = "note",
             group: str | None = None) -> str:
        """Text for an item planted in `group`. The group decides which nouns
        the item may name: a system may weigh whether an item belongs where it
        was written, and the benchmark should not plant one that does not."""
        return sentence(self.seed, self.scenario_id, self.variant, tag, words,
                        kind, self._ordinal(tag), self._roles.get(group or ""))

    def claim(self, tag: str, statement: str) -> str:
        """A canary in front of a statement the scenario writes itself.

        Used where a scenario needs two texts that genuinely contradict each
        other; the generator cannot produce a contradiction on request."""
        return f"{self.canary(tag)}: {statement}"

    def write(
        self,
        agent: Agent,
        tag: str | None = None,
        kind: Kind = "note",
        *,
        content: str | None = None,
        replaces: str | None = None,
        subject: str | None = None,
        words: int = 12,
    ) -> Receipt:
        if content is None:
            assert tag is not None, "write needs a tag or explicit content"
            content = self.text(tag, words, kind, agent.group)
        self._tick("write")
        receipt = self.system.write(
            agent, Write(content=content, kind=kind, replaces=replaces, subject=subject)
        )
        self._deadline_check("write")
        if tag is not None:
            tok = self.canary(tag)
            self._origin[tok] = agent.group
            self._kind[tok] = kind
        self._settled = False
        return receipt

    def announce(self, agent: Agent, receipt_id: str) -> Receipt:
        self._tick("announce")
        r = self.system.announce(agent, receipt_id)
        self._deadline_check("announce")
        self._settled = False
        return r

    def retract(self, agent: Agent, receipt_id: str) -> Receipt:
        self._tick("retract")
        r = self.system.retract(agent, receipt_id)
        self._deadline_check("retract")
        self._settled = False
        return r

    def read(self, agent: Agent) -> Read:
        if not self._settled:
            self._tick("settle")
            self.system.settle()
            self._settled = True
        self._tick("read")
        read = self.system.read(agent)
        self._deadline_check("read")
        return read

    # --- inspecting a read ------------------------------------------------

    @staticmethod
    def items_with(read: Read, token: str, *, include_events: bool = False) -> list[Shown]:
        """Items whose content carries the token. Withdrawal events are
        excluded unless asked for: an event says an item is gone, so counting
        it as the item still being shown would invert every measure."""
        return [
            i
            for i in read.items
            if token in i.content and (include_events or i.event is None)
        ]

    @staticmethod
    def events_for(read: Read, token: str) -> list[Shown]:
        return [i for i in read.items if i.event == "withdrawn" and token in i.content]

    def shows(self, read: Read, token: str) -> bool:
        return bool(self.items_with(read, token))

    @staticmethod
    def words_of(read: Read) -> int:
        """The benchmark's own count of what a reader was shown. A system's
        self-reported `words` is never used for scoring."""
        return sum(len(i.content.split()) for i in read.items)

    def true_origin(self, token: str) -> str | None:
        return self._origin.get(token)

    def true_kind(self, token: str) -> Kind | None:
        return self._kind.get(token)

    # --- recording --------------------------------------------------------

    def check(self, name: str, passed: bool, **detail) -> bool:
        self.checks.append(
            Check(id=f"{self.scenario_id}-{name}", passed=bool(passed), detail=detail)
        )
        return bool(passed)

    def absent(self, read: Read, token: str, name: str, **detail) -> bool:
        found = self.items_with(read, token)
        return self.check(
            name, not found, shown=[i.origin for i in found], **detail
        )

    def admitted(self, agent: Agent, tag: str, name: str = "plant-admitted") -> bool:
        """The precondition of every absence.

        A measure whose pass condition is "the reader was not shown X" is
        satisfied for free by a system that never held X at all — the absence
        holds because nothing was ever admitted. So before an absence is
        checked, the plant is shown to a reader plainly entitled to it, and a
        system that declined the write fails here, where the failure names
        what happened, rather than passing the measure it was meant to face.
        """
        return self.present(self.read(agent), self.canary(tag), name, tag=tag)

    def present(self, read: Read, token: str, name: str, **detail) -> bool:
        return self.check(name, self.shows(read, token), **detail)

    def skip_unless(self, condition: bool, why: str) -> None:
        if not condition:
            raise Skip(why)


# --- registry -------------------------------------------------------------

Measure = Callable[[Ctx], None]
_REGISTRY: dict[str, tuple[str, str, Measure]] = {}


def scenario(measure: str, family: str, doc: str = "") -> Callable[[Measure], Measure]:
    """Register a measure. `measure` is its id (e.g. "C1"), `family` its
    letter. Each measure is run once per variant."""

    def wrap(fn: Measure) -> Measure:
        if measure in _REGISTRY:
            raise ValueError(f"duplicate measure id {measure}")
        _REGISTRY[measure] = (family, doc or (fn.__doc__ or "").strip(), fn)
        return fn

    return wrap


def registry() -> dict[str, tuple[str, str, Measure]]:
    import bench.families  # noqa: F401  (registers every measure on import)

    return dict(_REGISTRY)


def run_scenario(
    system: MemorySystem,
    measure: str,
    variant: int,
    seed: int,
    declarations: Declarations,
    timeout: float | None = None,
) -> ScenarioResult:
    family, _doc, fn = registry()[measure]
    scenario_id = f"{measure}-{variant:03d}"
    ctx = Ctx(system, scenario_id, variant, seed, declarations, timeout=timeout)
    try:
        fn(ctx)
    except Skip as exc:
        # Not applicable to this system's declared policy: no score either way.
        return ScenarioResult(
            id=scenario_id, measure=measure, family=family, variant=variant,
            passed=None, unsupported=False, skipped=True, checks=[], reason=str(exc),
        )
    except Timeout as exc:
        return ScenarioResult(
            id=scenario_id, measure=measure, family=family, variant=variant,
            passed=False, unsupported=False, checks=ctx.checks,
            reason=f"timeout: {exc}",
        )
    except Unsupported as exc:
        return ScenarioResult(
            id=scenario_id, measure=measure, family=family, variant=variant,
            passed=False, unsupported=True, checks=ctx.checks, reason=str(exc),
        )
    except Exception:  # a scenario must never take the run down
        return ScenarioResult(
            id=scenario_id, measure=measure, family=family, variant=variant,
            passed=False, unsupported=False, checks=ctx.checks,
            error=traceback.format_exc(limit=4),
        )
    passed = bool(ctx.checks) and all(c.passed for c in ctx.checks)
    return ScenarioResult(
        id=scenario_id, measure=measure, family=family, variant=variant,
        passed=passed, unsupported=False, checks=ctx.checks,
    )
