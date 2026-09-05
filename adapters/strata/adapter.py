"""Strata adapter.

Read `adapters/strata/README.md` before touching this file. In particular:
build the fleet in-process with explicit paths. Driving Strata through its
CLI or a running server once reached an operator's real store and destroyed
real memory — never do that here.

MAPPING (MODEL.md term -> Strata term)

    group           -> scope
    part of         -> chain edge; a container's directives bind the
                       contained scope, and its context does not
    listens to      -> reference edge; one hop, directed, not transitive
    owner           -> operator; its memory binds and is never judged
    note / rule     -> context / directive
    write           -> contribution, judged by the scope's scope-manager
    announce        -> publish act, judged by the publishing scope
    retract         -> withdraw (published items only; see below)
    read            -> composed perspective
    origin / via    -> origin_scope_id / relay_scope_id on a published item

TWO CONFIGURATIONS, and they are two systems, not one.

    StrataMemory          admission is a real model call — the system people
                          actually run. Needs a judge key. Slow, costed,
                          nondeterministic; use --repeat and read the band.

    StrataStubJudgeMemory admission is mechanical: every contribution is
                          accepted with its proposed classification. NOBODY
                          RUNS THIS. It exists to isolate the code paths a
                          model never sees — composition, cascade, budget,
                          forgetting — so a failure there is provably the
                          engine's and not a judge's. It changes what is in
                          memory, so it changes what a reader is shown, so it
                          is reported under its own system.id and is never
                          submittable.

WHAT STRATA CANNOT DO, raised as Unsupported so a run reports "cannot"
rather than "did not":

    retract of a note   retirement exists for binding items only; a note is
                        dropped when memory is next curated, not un-said by
                        act. See Strata issue #188 (closed: the owner's
                        control path is not part of the mechanism) and the
                        benchmark's own F0.
    multiple containers a scope has at most one chain parent.

KNOWN FAILURES, expected and understood before the first run: nothing in a
composed read carries a withdrawal EVENT, and nothing reaches a scope that
absorbed a claim into its own memory rather than relaying it. That is Strata
issue #186, open, and it is why S4b and S7 should fail. The engine version
under test is release-blocked on it.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from bench.adapter.protocol import (
    Agent,
    Declarations,
    Info,
    Read,
    Receipt,
    Shown,
    Unsupported,
    World,
    Write,
)

_KIND = {"note": "context", "rule": "directive"}
_UNKIND = {"context": "note", "directive": "rule"}


@dataclass
class _Held:
    """What a receipt id refers to, so announce/retract can find it again."""

    group: str
    content: str
    kind: str          # benchmark kind: note | rule
    subject: str | None
    published_id: str | None = None   # set once announced


class _StrataBase:
    """Everything both configurations share. Subclasses supply the judge."""

    name = "strata"
    system_id = "strata"

    def __init__(self, workdir: str | None = None) -> None:
        self._root = Path(workdir) if workdir else None
        self._tmp: Path | None = None
        self._held: dict[str, _Held] = {}
        self._n = 0
        # Imported here, not at module scope: the benchmark itself does not
        # depend on Strata, and this file must import cleanly without it.
        from strata import __version__ as strata_version  # noqa: PLC0415

        self._version = strata_version

    # -- identity -----------------------------------------------------------

    def info(self) -> Info:
        return Info(
            id=self.system_id,
            name="Strata",
            version=self._version,
            declarations=Declarations(
                notes_flow_down=False,          # a chain edge carries directives only
                listening_is_transitive=False,  # a publication travels one edge
                multiple_containers=False,      # at most one chain parent
            ),
        )

    # -- world --------------------------------------------------------------

    def world(self, world: World) -> None:
        """Replace the fleet and wipe all memory.

        `part_of` is a tree (the system declares multiple_containers=False), so
        a group's depth in that tree is its stratum ordinal. Strata only allows
        a chain edge between ADJACENT strata, which the depth assignment
        satisfies by construction.
        """
        self._teardown()
        self._tmp = Path(tempfile.mkdtemp(prefix="fmb-strata-", dir=self._root))
        self._held.clear()
        self._n = 0

        container = {g: c for g, c in world.part_of}
        for g, c in world.part_of:
            if g in container and container[g] != c:
                raise Unsupported("multiple_containers")

        def depth(g: str, seen: frozenset[str] = frozenset()) -> int:
            if g in seen:
                raise Unsupported("part_of cycle")
            c = container.get(g)
            return 0 if c is None else 1 + depth(c, seen | {g})

        depths = {g: depth(g) for g in world.groups}
        strata = sorted(set(depths.values()))

        lines = ["strata:"]
        for d in strata:
            lines += [f"  - id: L{d}", f"    name: L{d}", f"    ordinal: {d}"]
        lines.append("scopes:")
        for g in world.groups:
            lines += [f"  - id: {g}", f"    name: {g}", f"    stratum_id: L{depths[g]}"]
        lines.append("edges:")
        if not world.part_of and not world.listens_to:
            lines[-1] = "edges: []"
        for g, c in world.part_of:
            lines += [f"  - from: {g}", f"    to: {c}", "    kind: chain"]
        for g, src in world.listens_to:
            lines += [f"  - from: {g}", f"    to: {src}", "    kind: reference"]

        (self._tmp / "fleet.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (self._tmp / "summaries").mkdir()

        from strata.fleet_config import FleetConfig  # noqa: PLC0415
        from strata.migrator import run_migrations  # noqa: PLC0415
        from strata.record_store import RecordStore  # noqa: PLC0415
        from strata.summary_store import SummaryStore  # noqa: PLC0415

        run_migrations(str(self._tmp / "strata.db"))
        self._fleet = FleetConfig.load(self._tmp / "fleet.yaml")
        self._record = RecordStore(str(self._tmp / "strata.db"))
        self._summaries = SummaryStore(str(self._tmp / "summaries"))
        self._owner_groups = set(world.owner_groups)

    def _stratum(self, stratum_id: str):
        return next(s for s in self._fleet.strata if s.id == stratum_id)

    def _teardown(self) -> None:
        if self._tmp is not None and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
        self._tmp = None

    # -- writing ------------------------------------------------------------

    def _next_id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n:04d}"

    def _contributor(self, agent: Agent):
        from strata.record_store import ContributorRef  # noqa: PLC0415

        return ContributorRef(
            scope_id=agent.group,
            skill="bench",
            session_id=f"fmb-{agent.id}",
            ts="2026-09-04T00:00:00+00:00",
        )

    def write(self, agent: Agent, write: Write) -> Receipt:
        """An owner's write is operator memory; anyone else's is a contribution."""
        from strata.operator import operator_publish  # noqa: PLC0415

        rid = self._next_id("w")

        if agent.owner:
            if write.kind == "note":
                # Operator memory is directives only: everything the owner
                # attaches binds. There is no non-binding operator channel.
                raise Unsupported("owner note")
            item = operator_publish(
                agent.group,
                write.content,
                write.subject,
                record_store=self._record,
                summaries_dir=str(self._summaries.summaries_dir),
            )
            self._held[rid] = _Held(agent.group, write.content, write.kind, write.subject)
            self._held[rid].published_id = item.id
            return Receipt(id=rid, accepted=True)

        scope = self._fleet.get_scope(agent.group)
        if scope is None:
            return Receipt(id=rid, accepted=False, reason=f"no such group: {agent.group}")

        from strata.app import run_contribution  # noqa: PLC0415

        outcome = run_contribution(
            scope=scope,
            stratum=self._stratum(scope.stratum_id),
            content=write.content,
            proposed_classification=_KIND[write.kind],
            subject=write.subject,
            supersedes=self._held[write.replaces].published_id if write.replaces else None,
            contributor=self._contributor(agent),
            fleet=self._fleet,
            record_store=self._record,
            summary_store=self._summaries,
            scope_manager=self._judge(),
            summary_max_words=self._summary_max_words(),
        )
        accepted = outcome.decision.startswith("accept")
        self._held[rid] = _Held(agent.group, write.content, write.kind, write.subject)
        return Receipt(
            id=rid,
            accepted=accepted,
            reason=None if accepted else outcome.reasoning,
        )

    def announce(self, agent: Agent, receipt_id: str) -> Receipt:
        """Offer a held item outward — a judged publish act."""
        from strata.publication import propose_publish  # noqa: PLC0415

        held = self._held.get(receipt_id)
        if held is None:
            return Receipt(id=self._next_id("a"), accepted=False, reason="unknown receipt")

        rid = self._next_id("a")
        try:
            outcome = propose_publish(
                held.group,
                held.content,
                _KIND[held.kind],
                held.subject,
                [f"subject:{self._anchor_subject(receipt_id, held)}"],
                self._contributor(agent),
                fleet=self._fleet,
                record_store=self._record,
                summary_store=self._summaries,
                scope_manager=self._judge(),
            )
        except Exception as exc:  # a structural refusal, not a verdict
            return Receipt(id=rid, accepted=False, reason=str(exc))

        accepted = getattr(outcome, "decision", "") == "accept"
        if accepted:
            from strata.publication import read_publication  # noqa: PLC0415

            items = read_publication(held.group, summaries_dir=str(self._summaries.summaries_dir))
            match = next((i for i in items if i.content == held.content), None)
            self._held[rid] = _Held(held.group, held.content, held.kind, held.subject)
            self._held[rid].published_id = match.id if match else None
        return Receipt(id=rid, accepted=accepted, reason=None if accepted else "declined")

    @staticmethod
    def _anchor_subject(receipt_id: str, held: _Held) -> str:
        """Every publish act needs an anchor; a subject string is one.

        The benchmark's subject is optional, Strata's anchor is not. When an
        item has no subject, anchoring on its own receipt id is the faithful
        choice rather than a workaround: MODEL.md makes subject the thing that
        constructs contradiction ("two items on the same subject with
        incompatible content contradict"), so an item with no subject stands
        on no shared subject with anything — and a unique anchor says exactly
        that. Inventing a shared subject would invent a contradiction.
        """
        return held.subject or receipt_id

    def retract(self, agent: Agent, receipt_id: str) -> Receipt:
        """Withdraw a published item.

        A note that was never announced cannot be retracted: retirement exists
        for binding items only, and a note leaves when memory is next curated
        rather than by an act. Reported as Unsupported so the run says "cannot".
        """
        held = self._held.get(receipt_id)
        if held is None:
            return Receipt(id=self._next_id("r"), accepted=False, reason="unknown receipt")
        if held.published_id is None:
            raise Unsupported("retract of an unannounced item")

        from strata.publication import propose_withdraw  # noqa: PLC0415

        rid = self._next_id("r")
        try:
            outcome = propose_withdraw(
                held.group,
                held.published_id,
                self._contributor(agent),
                fleet=self._fleet,
                record_store=self._record,
                summary_store=self._summaries,
                scope_manager=self._judge(),
            )
        except Exception as exc:
            return Receipt(id=rid, accepted=False, reason=str(exc))
        return Receipt(id=rid, accepted=getattr(outcome, "decision", "") == "accept")

    # -- reading ------------------------------------------------------------

    def read(self, agent: Agent) -> Read:
        """Everything the agent is shown, acting from its group."""
        from strata.operator import read_operator_layer  # noqa: PLC0415
        from strata.perspective import compose_perspective  # noqa: PLC0415
        from strata.publication import read_publication  # noqa: PLC0415

        sdir = str(self._summaries.summaries_dir)
        perspective = compose_perspective(
            agent.group,
            fleet=self._fleet,
            summary_store=self._summaries,
            publication_reader=lambda s: read_publication(s, summaries_dir=sdir),
            operator_reader=lambda s: read_operator_layer(s, summaries_dir=sdir),
        )

        shown: list[Shown] = []
        for layer in perspective["layers"]:
            origin = layer["scope_id"]
            binding = bool(layer.get("binding"))

            for directive in self._layer_directives(layer):
                shown.append(
                    Shown(
                        content=directive["content"],
                        kind="rule",
                        origin=directive.get("source_scope_id") or origin,
                        binding=binding,
                        receipt=directive.get("id"),
                    )
                )

            context = self._layer_context(layer)
            if context:
                shown.append(
                    Shown(content=context, kind="note", origin=origin, binding=False)
                )

            for item in (layer.get("publication") or {}).get("items", []):
                shown.append(
                    Shown(
                        content=item["content"],
                        kind=_UNKIND.get(item.get("kind", "context"), "note"),
                        origin=item.get("origin_scope_id") or origin,
                        binding=False,
                        via=item.get("relay_scope_id"),
                        attributed_to=item.get("origin_scope_id"),
                        receipt=item.get("id"),
                    )
                )
        # No `event="withdrawn"` is ever emitted: a composed read carries no
        # withdrawal event, so a reader is never TOLD an item was retracted —
        # it simply stops appearing. Strata issue #186. Emitting nothing is the
        # honest answer; inventing one would score a pass the engine has not
        # earned.
        return Read(items=tuple(shown), words=sum(len(s.content.split()) for s in shown))

    @staticmethod
    def _layer_directives(layer: dict) -> list[dict]:
        """Directives from either layer shape: own summary, or ancestor."""
        if "summary" in layer:
            return list(layer["summary"].get("directives") or [])
        if "directives" in layer:
            return list(layer["directives"] or [])
        if "operator_memory" in layer:
            return list((layer["operator_memory"] or {}).get("directives") or [])
        return []

    @staticmethod
    def _layer_context(layer: dict) -> str:
        """Context belongs to the reader's OWN layer only; ancestors carry none."""
        if "summary" in layer:
            return (layer["summary"].get("context") or "").strip()
        return ""

    def settle(self) -> None:
        """Strata decides synchronously — a contribution is judged before its
        call returns, and mechanical propagation runs under the same lock."""

    # -- configuration hooks ------------------------------------------------

    def _summary_max_words(self) -> int:
        from strata.settings import get_settings  # noqa: PLC0415

        return get_settings().summary_max_words

    def _judge(self):
        raise NotImplementedError


class StrataMemory(_StrataBase):
    """The system people actually run: admission is a real model call."""

    system_id = "strata"

    def _judge(self):
        from strata.scope_manager import ScopeManager  # noqa: PLC0415

        return ScopeManager()


class StrataStubJudgeMemory(_StrataBase):
    """Instrumented configuration. NOBODY RUNS THIS.

    Admission is mechanical — every contribution is accepted with the
    classification its writer proposed, and every publish act is accepted.
    It exists to isolate the code paths a model never sees: composition,
    relay cascade, budget, forgetting. A failure under this configuration is
    provably the engine's, because no judgment was involved.

    It changes what is in memory and therefore what a reader is shown, so it
    is a different system from `strata` and is reported under its own id.
    """

    system_id = "strata-stubjudge"

    def _judge(self):
        return _MechanicalJudge()


class _MechanicalJudge:
    """Accept everything, in the writer's own words. No model call.

    The resulting summary is built with the ENGINE's own `_apply_amendment`,
    not by hand: a stub that wrote summaries its own way would be measuring
    the stub. This applies the same ops the real judge would emit and lets
    Strata do the applying.
    """

    def judge(self, **kwargs):
        from strata.scope_manager import (  # noqa: PLC0415
            DirectiveOp,
            ScopeManagerJudgment,
            _apply_amendment,
        )

        contribution = kwargs.get("new_contribution")
        scope = kwargs.get("scope")
        current = kwargs.get("current_summary")
        proposed = getattr(contribution, "proposed_classification", "context")

        if proposed == "directive":
            ops = [DirectiveOp(op="append")]
            new_context = None
        else:
            ops = []
            existing = (getattr(current, "context", "") or "").strip()
            body = getattr(contribution, "content", "")
            new_context = f"{existing}\n{body}".strip() if existing else body

        new_summary = _apply_amendment(
            scope=scope,
            current_summary=current,
            contribution=contribution,
            ops=ops,
            new_context=new_context,
        )
        return ScopeManagerJudgment(
            new_summary=new_summary,
            decision=f"accept_as_{proposed}",
            reasoning="mechanical admission (instrumented configuration)",
            directive_ops=ops,
            new_context=new_context,
        )

    def judge_publication(self, **kwargs):
        from strata.scope_manager import PublicationJudgment  # noqa: PLC0415

        return PublicationJudgment(
            decision="accept",
            reasoning="mechanical admission (instrumented configuration)",
        )

    def judge_bootstrap_publication(self, **kwargs):
        raise Unsupported("bootstrap publication")
