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
    retract         -> withdraw of the published item, and a
                       superseding contribution against the scope's own memory
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

READS DRAIN FIRST (ADR 0014 D6). `read()` mirrors the MCP server's read
path: pending input changes are drained under the scope's lock before the
perspective is composed, so an ancestor's new directive, an operator
correction and an upstream withdrawal all take effect on the next read with
no further write. Under `strata` that drain is a model call; under
`strata-stubjudge` it is the mechanical judge, which changes nothing.

WHAT STRATA CANNOT DO, raised as Unsupported so a run reports "cannot"
rather than "did not":

    owner note          operator memory is directives only; everything the
                        owner attaches binds.
    retract of          the owner's control path is not an agent act
    operator memory     (Strata issue #188, closed).
    multiple containers a scope has at most one chain parent.

KNOWN GAP, understood before the run: a scope is never told about its OWN
retraction. ADR 0014 D1 — "a scope's own contribution is not a trigger; it
already has a path" — and `change_events.affected_scopes` excludes the source
scope for every publication change, so an agent retracting its group's own
note leaves no withdrawal notice for that group's readers. The item does
leave (the retraction contribution supersedes it), but nobody is TOLD. That
is F0's "retraction-announced" check, and Strata issue #197. This adapter
emits no event there: inventing one would score a pass the engine has not
earned.
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
_RETRACTION_PREFIX = "Retract "


def _retraction_text(held: "_Held") -> str:
    """The wording of a retraction contribution.

    It never restates the retracted text. A retraction that repeats the claim
    puts the false claim back in front of the judge and leaves it in the
    scope's own words if the judge admits the retraction verbatim — which is
    the opposite of retracting it.
    """
    subject = held.subject or "(no subject)"
    return (
        f"{_RETRACTION_PREFIX}{held.kind} {held.contribution_id} on {subject}: "
        "it no longer holds; remove it from memory, do not restate it."
    )
_UNKIND = {"context": "note", "directive": "rule"}


@dataclass
class _Held:
    """What a receipt id refers to, so announce/retract can find it again."""

    group: str
    content: str
    kind: str          # benchmark kind: note | rule
    subject: str | None
    published_id: str | None = None   # set once announced (a published item id)
    contribution_id: str | None = None  # the record row a write produced
    retracted: bool = False           # taken back; the group no longer holds it


class _StrataBase:
    """Everything both configurations share. Subclasses supply the judge."""

    name = "strata"
    system_id = "strata"

    def __init__(self, workdir: str | None = None) -> None:
        self._root = Path(workdir) if workdir else None
        self._tmp: Path | None = None
        self._held: dict[str, _Held] = {}
        # Strata item id (published item, or contribution) -> bench receipt id.
        # A withdrawal notice names a Strata id; the benchmark grades receipts.
        self._by_item: dict[str, str] = {}
        self._bound = 500
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
        self._by_item.clear()
        self._n = 0
        # MODEL.md's `bound` is "the maximum size of any one read, in words",
        # and the World hands it to the system as the target. Strata's own word
        # budget is the same quantity for the scope's own memory, so it is set
        # from the bound rather than left at the engine default.
        self._bound = world.bound

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
                # Without a fleet this primitive informs nobody (ADR 0014 D3:
                # "a call without one informs nobody, which is a silent gap"),
                # so no descendant ever refreshes and an owner rule never takes
                # effect on a reader's next read.
                fleet=self._fleet,
            )
            self._held[rid] = _Held(agent.group, write.content, write.kind, write.subject)
            self._held[rid].published_id = item.id
            self._by_item[item.id] = rid
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
            # A contribution supersedes a CONTRIBUTION (record_store's
            # `supersedes` is a contribution id and a directive id IS its
            # contribution id) — never a published item id, which is what this
            # adapter used to pass and why a replacement replaced nothing.
            supersedes=(
                self._held[write.replaces].contribution_id
                if write.replaces and write.replaces in self._held
                else None
            ),
            contributor=self._contributor(agent),
            fleet=self._fleet,
            record_store=self._record,
            summary_store=self._summaries,
            scope_manager=self._judge(),
            summary_max_words=self._summary_max_words(),
        )
        accepted = outcome.decision.startswith("accept")
        self._held[rid] = _Held(
            agent.group,
            write.content,
            write.kind,
            write.subject,
            contribution_id=outcome.contribution_id,
        )
        self._by_item[outcome.contribution_id] = rid
        return Receipt(
            id=rid,
            accepted=accepted,
            reason=None if accepted else outcome.reasoning,
        )

    def announce(self, agent: Agent, receipt_id: str) -> Receipt:
        """Offer a held item outward — a judged publish act.

        Two shapes, and the second is what MODEL.md calls a relay:

        * the receipt names something this adapter wrote for the agent's own
          group: an ordinary publish act from that group;
        * the receipt names a published item the agent was SHOWN (the
          `receipt` on a Shown from another group's publication): a
          REPUBLICATION, made with Strata's own relay path so that
          `origin_scope_id` and `relay_scope_id` are derived by the engine
          from the source item. Provenance is never asserted by this adapter —
          `propose_publish` refuses to take an origin from its caller.
        """
        from strata.publication import propose_publish, read_publication  # noqa: PLC0415

        rid = self._next_id("a")
        held = self._held.get(receipt_id)

        if held is None:
            return self._announce_relay(agent, receipt_id, rid)

        if held.retracted:
            # "An announcement can only be of something the group actually
            # holds" (MODEL.md). This is the adapter's own receipt table
            # answering, not a Strata refusal: `propose_publish` takes the
            # content it is handed, and by this point the content is no longer
            # in the scope's memory — so announcing it would put back what the
            # retraction took out. Saying "accepted" for something the group
            # stopped holding is the answer that would be false.
            return Receipt(id=rid, accepted=False, reason="not held: retracted")

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
                publication_max_words=self._bound,
            )
        except Exception as exc:  # a structural refusal, not a verdict
            return Receipt(id=rid, accepted=False, reason=str(exc))

        accepted = getattr(outcome, "decision", "") == "accept"
        if accepted:
            # The publish ACT id is the published item's id (ADR 0007 D1),
            # so there is no content matching to get wrong when two items
            # say the same thing.
            item_id = outcome.act_id
            self._held[rid] = _Held(
                held.group, held.content, held.kind, held.subject,
                published_id=item_id, contribution_id=held.contribution_id,
            )
            # The item is now announced under BOTH receipts: the benchmark
            # retracts the write's receipt as often as the announcement's.
            held.published_id = item_id
            self._by_item[item_id] = receipt_id
            _ = read_publication  # imported for the relay path's docstring parity
        return Receipt(id=rid, accepted=accepted, reason=None if accepted else "declined")

    def _announce_relay(self, agent: Agent, receipt_id: str, rid: str) -> Receipt:
        """Republish an item the agent was shown, from the agent's own group.

        The receipt is a Strata published-item id. Its source must be a scope
        the agent's group actually composes one hop away — its chain parent or
        a scope it references — which is the same surface the MCP server
        enforces before relaying (`_relay_source_scope_ids`). Origin and relay
        provenance come from `propose_publish` reading the source item, not
        from anything said here.
        """
        from strata.publication import propose_publish, read_publication  # noqa: PLC0415

        sdir = str(self._summaries.summaries_dir)
        parent = self._fleet.inter_stratum_parent(agent.group)
        sources = [s.id for s in self._fleet.references_from(agent.group)]
        if parent is not None:
            sources.append(parent.id)

        for source_id in sources:
            item = next(
                (i for i in read_publication(source_id, summaries_dir=sdir) if i.id == receipt_id),
                None,
            )
            if item is None:
                continue
            try:
                outcome = propose_publish(
                    agent.group,
                    item.content,
                    item.kind,
                    item.subject,
                    [f"subject:{item.subject or item.id}"],
                    self._contributor(agent),
                    fleet=self._fleet,
                    record_store=self._record,
                    summary_store=self._summaries,
                    scope_manager=self._judge(),
                    relay_source_scope_id=source_id,
                    relay_source_item_id=item.id,
                    publication_max_words=self._bound,
                )
            except Exception as exc:
                return Receipt(id=rid, accepted=False, reason=str(exc))
            accepted = getattr(outcome, "decision", "") == "accept"
            if accepted:
                self._held[rid] = _Held(
                    agent.group,
                    item.content,
                    _UNKIND.get(item.kind, "note"),
                    item.subject,
                    published_id=outcome.act_id,
                )
                self._by_item[outcome.act_id] = rid
            return Receipt(id=rid, accepted=accepted, reason=None if accepted else "declined")

        return Receipt(id=rid, accepted=False, reason="unknown receipt")

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
        """Take back a write or an announcement.

        A published item is withdrawn — the judged act on the scope's outward
        face — and that is what emits the withdrawal change events readers
        are told by. But the outward face is not the scope's memory: the item
        is still in the scope's own summary, so a retraction is ALSO an
        ordinary contribution that supersedes the original.

        That contribution is the whole of the retraction for a note that was
        never announced. ADR 0014's own framing: a changed input triggers a
        judge cycle and the judge decides — "if someone in the scope says
        'this is false' it's the ordinary contribution path". Nothing here is
        `Unsupported` any more.

        The contribution never restates the retracted text. It names the
        contribution id and the subject, and asks for removal: restating a
        false claim to get rid of it puts it back in front of the judge, and
        would leave it in the reader's own words in memory.
        """
        held = self._held.get(receipt_id)
        if held is None:
            return Receipt(id=self._next_id("r"), accepted=False, reason="unknown receipt")

        rid = self._next_id("r")
        withdrawn: bool | None = None

        if held.published_id is not None and held.contribution_id is None:
            # Operator memory: the owner's own control path, not an agent act.
            raise Unsupported("retract of operator memory")

        if held.published_id is not None:
            from strata.publication import propose_withdraw  # noqa: PLC0415

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
            withdrawn = getattr(outcome, "decision", "") == "accept"

        retracted: bool | None = None
        if held.contribution_id is not None:
            scope = self._fleet.get_scope(held.group)
            from strata.app import run_contribution  # noqa: PLC0415

            outcome = run_contribution(
                scope=scope,
                stratum=self._stratum(scope.stratum_id),
                content=_retraction_text(held),
                proposed_classification=_KIND[held.kind],
                subject=held.subject,
                supersedes=held.contribution_id,
                contributor=self._contributor(agent),
                fleet=self._fleet,
                record_store=self._record,
                summary_store=self._summaries,
                scope_manager=self._judge(),
                summary_max_words=self._summary_max_words(),
            )
            retracted = outcome.decision.startswith("accept")

        accepted = bool(withdrawn) or bool(retracted)
        if accepted:
            held.retracted = True
            # Every receipt that names this item is retracted, not just the one
            # the caller passed: a write and its announcement are two receipts
            # for one claim.
            for other in self._held.values():
                if other.contribution_id is not None and (
                    other.contribution_id == held.contribution_id
                ):
                    other.retracted = True
        return Receipt(
            id=rid,
            accepted=accepted,
            reason=None if accepted else "declined",
        )

    # -- reading ------------------------------------------------------------

    def read(self, agent: Agent) -> Read:
        """Everything the agent is shown, acting from its group.

        Mirrors the MCP server's read path (ADR 0014 D6): the scope's pending
        input changes are DRAINED before composition, so nobody reads a scope
        without the engine first attempting to bring it up to date. That is
        where an ancestor's new directive, an operator correction and an
        upstream withdrawal actually take effect for this reader.

        The pending events are snapshotted BEFORE the drain because the drain
        consumes them: `compose_perspective` filters `input_changes` to
        UNPROCESSED events (ADR 0014 D5 — "an event is consumed once a refresh
        has processed it"), so a read that successfully drains would otherwise
        compose an empty `input_changes` and the reader would never be told.
        Both are used: the snapshot is what this read processed, and the
        composed section is whatever the drain could not.
        """
        from strata.app import DrainFailed, drain_is_noop, drain_scope  # noqa: PLC0415
        from strata.operator import read_operator_layer  # noqa: PLC0415
        from strata.perspective import compose_perspective  # noqa: PLC0415
        from strata.publication import read_publication  # noqa: PLC0415

        pending = self._record.list_change_events(scope_id=agent.group, unprocessed_only=True)
        if not drain_is_noop(
            agent.group,
            fleet=self._fleet,
            record_store=self._record,
            summary_store=self._summaries,
        ):
            try:
                drain_scope(
                    agent.group,
                    fleet=self._fleet,
                    record_store=self._record,
                    summary_store=self._summaries,
                    scope_manager=self._judge(),
                    summary_max_words=self._summary_max_words(),
                )
            except DrainFailed:
                # A read must not fail because a refresh could not run (ADR
                # 0014 D6): the events stay pending and are still composed.
                pass

        sdir = str(self._summaries.summaries_dir)
        perspective = compose_perspective(
            agent.group,
            fleet=self._fleet,
            summary_store=self._summaries,
            publication_reader=lambda s: read_publication(s, summaries_dir=sdir),
            operator_reader=lambda s: read_operator_layer(s, summaries_dir=sdir),
            change_event_reader=lambda s: self._record.list_change_events(
                scope_id=s, unprocessed_only=False
            ),
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
                        # ADR 0013 D4: `origin_scope_id` is the ULTIMATE author
                        # and is set only on a relay. MODEL.md's `via` is "the
                        # intermediate group whose announcement the item
                        # reached the reader through" — that is the scope whose
                        # publication is being composed here, NOT Strata's
                        # `relay_scope_id`, which names the predecessor the
                        # copy was taken FROM (for a one-hop relay, the origin
                        # itself). `attributed_to` is not set: MODEL.md
                        # reserves it for a RESTATEMENT of another group's
                        # claim, and a relay is the claim itself.
                        origin=item.get("origin_scope_id") or origin,
                        binding=False,
                        via=origin if item.get("origin_scope_id") else None,
                        receipt=item.get("id"),
                    )
                )

        shown.extend(self._withdrawal_events(pending, perspective["input_changes"]))
        return Read(items=tuple(shown), words=sum(len(s.content.split()) for s in shown))

    def _withdrawal_events(self, drained, composed) -> list[Shown]:
        """The `withdrawn` notices this read delivers (ADR 0014 D5).

        One per change event of kind `withdrawn` — an engine-written row, not
        an inference: `propose_withdraw` and the relay cascade both emit it
        carrying the item's own content as `before`, which is what makes a
        notice identify what was pulled rather than merely say that something
        was. This is D5's notice reaching the READER; before ADR 0014 nothing
        in a composed read carried it, which is why this adapter used to
        return none.
        """
        seen: set[tuple[str, str]] = set()
        events: list[Shown] = []
        rows = [
            {
                "change_id": e.change_id,
                "item_id": e.item_id,
                "kind": e.kind,
                "before": e.before,
                "source_scope_id": e.source_scope_id,
            }
            for e in drained
        ] + list(composed)
        for row in rows:
            if row["kind"] != "withdrawn" or not row.get("before"):
                continue
            key = (row["change_id"], row["item_id"])
            if key in seen:
                continue
            seen.add(key)
            receipt = self._by_item.get(row["item_id"], row["item_id"])
            held = self._held.get(receipt)
            events.append(
                Shown(
                    content=row["before"],
                    kind=held.kind if held else "note",
                    origin=row["source_scope_id"] or (held.group if held else ""),
                    binding=False,
                    receipt=receipt,
                    event="withdrawn",
                )
            )
        return events

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
        """The scope's own word budget — the World's `bound`, not a setting.

        The benchmark states the target per read (`World.bound`); leaving the
        engine default of 500 against a stated bound of 400 would measure the
        default rather than the system. Threaded as a parameter, so nothing
        global is mutated and two adapters can coexist in one process.
        """
        return self._bound

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
        return _MechanicalJudge(self._record)


class _MechanicalJudge:
    """Accept everything, in the writer's own words. No model call.

    The resulting summary is built with the ENGINE's own `_apply_amendment` /
    `_apply_batch_amendment`, not by hand: a stub that wrote summaries its own
    way would be measuring the stub. This applies the same ops the real judge
    would emit and lets Strata do the applying.

    It is handed the record store so it can read the CONTENT of a contribution
    that a new one supersedes — a real judge is shown the summary it is
    amending and the contribution's `supersedes` reference; a mechanical one
    has to look the text up to know which context line the replacement
    replaces. Nothing is decided with it; it is only how "remove the line that
    said X" is carried out without the stub inventing its own summary format.

    Three rules, and nothing else:

    * a directive is appended; a context line is appended to the context;
    * a contribution that SUPERSEDES another removes the superseded row or
      line first — and adds nothing back when it is a retraction, whose whole
      content is "remove this";
    * an input-change refresh changes nothing at all. Mechanical means
      mechanical: the notice is accepted, the memory is left exactly as it
      was. Every judgment a refresh could reach is a judgment, and this
      configuration exists precisely to have none.
    """

    def __init__(self, record_store=None) -> None:
        self._record = record_store

    # -- the rules ---------------------------------------------------------

    def _superseded_content(self, contribution) -> str | None:
        target = getattr(contribution, "supersedes", None)
        if not target or self._record is None:
            return None
        row = self._record.get_contribution(target)
        return row.content if row is not None else None

    @staticmethod
    def _is_retraction(contribution) -> bool:
        return bool(getattr(contribution, "supersedes", None)) and getattr(
            contribution, "content", ""
        ).startswith(_RETRACTION_PREFIX)

    @staticmethod
    def _is_refresh(contribution, mode: str) -> bool:
        return mode == "input_change_refresh" or (
            getattr(contribution, "subject", None) == "manager-refresh"
        )

    def _amendment(self, contribution, current, *, attribute: bool):
        """The ops and context one contribution produces. No verdict here."""
        from strata.scope_manager import DirectiveOp  # noqa: PLC0415

        cid = getattr(contribution, "id", None)
        target = getattr(contribution, "supersedes", None)
        retraction = self._is_retraction(contribution)
        proposed = getattr(contribution, "proposed_classification", "context")
        attribution = {"contribution_id": cid} if attribute else {}

        if proposed == "directive":
            ops: list = []
            if target:
                # A directive id IS its contribution id, so the id the
                # contribution supersedes names the row to remove. An op
                # naming something that is not in this summary is dropped by
                # the engine's own validation, which is the right outcome.
                ops.append(
                    DirectiveOp(op="retire" if retraction else "supersede", id=target, **attribution)
                )
            if not retraction:
                ops.append(DirectiveOp(op="append", **attribution))
            return ops, None

        existing = (getattr(current, "context", "") or "").strip()
        lines = [line for line in existing.split("\n") if line.strip()]
        superseded = self._superseded_content(contribution)
        if superseded:
            dropped = {ln.strip() for ln in superseded.split("\n") if ln.strip()}
            lines = [line for line in lines if line.strip() not in dropped]
        if not retraction:
            lines.append(getattr(contribution, "content", ""))
        return [], "\n".join(lines).strip()

    # -- the judge surface -------------------------------------------------

    def judge(self, **kwargs):
        from strata.scope_manager import (  # noqa: PLC0415
            ScopeManagerJudgment,
            _apply_amendment,
        )

        contribution = kwargs.get("new_contribution")
        scope = kwargs.get("scope")
        current = kwargs.get("current_summary")
        mode = kwargs.get("mode", "ordinary")
        proposed = getattr(contribution, "proposed_classification", "context")

        if self._is_refresh(contribution, mode):
            ops, new_context, proposed = [], None, "context"
        else:
            ops, new_context = self._amendment(contribution, current, attribute=False)

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
            # ADR 0014 D4: the wave id and hop are PARAMETERS of the call,
            # carried back on the judgment so whatever the engine derives from
            # this refresh inherits them. A judgment that dropped them would
            # restart the wave and break termination.
            change_id=kwargs.get("change_id"),
            hop=kwargs.get("hop", 0),
        )

    def judge_batch(self, **kwargs):
        """Judge a coalesced batch — what a drain of several notices produces.

        A batch of one never reaches here: `_judge_batch_and_record` routes it
        to `judge` verbatim (ADR 0011 D3), which is most drains. This is the
        coalesced case, and it is built with `_apply_batch_amendment` for the
        same reason `judge` uses `_apply_amendment` — the engine applies its
        own amendments.
        """
        from strata.scope_manager import (  # noqa: PLC0415
            BatchVerdict,
            ScopeManagerBatchJudgment,
            _apply_batch_amendment,
        )

        scope = kwargs.get("scope")
        current = kwargs.get("current_summary")
        mode = kwargs.get("mode", "ordinary")
        contributions = list(kwargs.get("new_contributions") or [])

        ops: list = []
        new_context: str | None = None
        verdicts: list[BatchVerdict] = []
        working = current
        for contribution in contributions:
            if self._is_refresh(contribution, mode):
                decision = "accept_as_context"
            else:
                member_ops, member_context = self._amendment(
                    contribution, working, attribute=True
                )
                ops.extend(member_ops)
                if member_context is not None:
                    new_context = member_context
                    working = _apply_batch_amendment(
                        scope=scope,
                        current_summary=working,
                        contributions={c.id: c for c in contributions},
                        ops=[],
                        new_context=member_context,
                    )
                proposed = getattr(contribution, "proposed_classification", "context")
                decision = f"accept_as_{proposed}"
            verdicts.append(
                BatchVerdict(
                    contribution_id=contribution.id,
                    decision=decision,
                    reasoning="mechanical admission (instrumented configuration)",
                )
            )

        new_summary = _apply_batch_amendment(
            scope=scope,
            current_summary=current,
            contributions={c.id: c for c in contributions},
            ops=ops,
            new_context=new_context,
        )
        return ScopeManagerBatchJudgment(
            new_summary=new_summary,
            verdicts=verdicts,
            directive_ops=ops,
            new_context=new_context,
            change_ids=list(dict.fromkeys(kwargs.get("change_ids") or ())),
            hop=kwargs.get("hop", 0),
        )

    def judge_publication(self, **kwargs):
        from strata.scope_manager import PublicationJudgment  # noqa: PLC0415

        return PublicationJudgment(
            decision="accept",
            reasoning="mechanical admission (instrumented configuration)",
        )

    def judge_bootstrap_publication(self, **kwargs):
        raise Unsupported("bootstrap publication")
