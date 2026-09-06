"""Family P — Policy conformance. Not scored as governance.

These measures test rules the promise does not force (MODEL.md § "Forced by
the promise, and chosen"). Each grades the system against what it declared,
never against a preferred answer — and against its BEHAVIOUR, not against
the declaration itself: a declaration is never wrong as a choice and never
sufficient as an answer.
"""

from bench.scenario import Ctx, scenario


@scenario("P1", "P")
def p1(ctx: Ctx) -> None:
    """Downward notes match the declaration. Either the container's notes do
    not reach its parts, or they reach them plainly labelled as notes from
    the container — never as rules, never binding, never mislabelled."""
    g = ctx.standard()
    ctx.write(ctx.agent(g["support"]), "note")
    read = ctx.read(ctx.agent(g["tier2"]))
    shown = ctx.items_with(read, ctx.canary("note"))
    if not ctx.declarations.notes_flow_down:
        ctx.check("declared-not-to-flow-and-did-not", not shown,
                  shown=[i.origin for i in shown])
        return
    ctx.check("flows-as-declared", bool(shown))
    ctx.check("labelled-as-note", all(i.kind == "note" for i in shown))
    ctx.check("not-binding", all(not i.binding for i in shown))
    ctx.check("origin-is-container", all(i.origin == g["support"] for i in shown),
              got=[i.origin for i in shown])


@scenario("P2", "P")
def p2(ctx: Ctx) -> None:
    """Announcement reach matches the declaration. Either announcements stop
    at one hop, or they travel further and every hop they travelled is
    visible in `via`."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["finance"]), "claim")
    ctx.announce(ctx.agent(g["finance"]), r.id)
    tok = ctx.canary("claim")
    ctx.present(ctx.read(ctx.agent(g["billing"])), tok, "direct-listener-heard")
    read = ctx.read(ctx.agent(g["support"]))
    shown = ctx.items_with(read, tok)
    if not ctx.declarations.listening_is_transitive:
        ctx.check("declared-one-hop-and-stopped", not shown,
                  leaked_to=g["support"])
        return
    ctx.check("travelled-as-declared", bool(shown))
    ctx.check("hops-visible", all(i.via is not None for i in shown),
              via=[i.via for i in shown])


@scenario("P3", "P")
def p3(ctx: Ctx) -> None:
    """Multiple containers match the declaration. A group inside two
    containers is bound by both, each rule keeps its true origin, and a
    conflict between them is shown as a conflict rather than silently
    resolved. Not issued to systems that declare containment is a tree."""
    ctx.skip_unless(ctx.declarations.multiple_containers,
                    "system declares containment is a tree")
    g = {r: ctx.gid(r) for r in ("eng", "infra", "platform")}
    ctx.build(
        groups=g.values(),
        part_of=[(g["platform"], g["eng"]), (g["platform"], g["infra"])],
    )
    subj = f"deploys-{v}"
    ctx.write(ctx.agent(g["eng"]), "eng", kind="rule", subject=subj)
    ctx.write(ctx.agent(g["infra"]), "infra", kind="rule", subject=subj)
    read = ctx.read(ctx.agent(g["platform"]))
    eng = ctx.items_with(read, ctx.canary("eng"))
    infra = ctx.items_with(read, ctx.canary("infra"))
    ctx.check("both-containers-bind", bool(eng) and bool(infra),
              eng=len(eng), infra=len(infra))
    ctx.check("origins-true",
              all(i.origin == g["eng"] for i in eng)
              and all(i.origin == g["infra"] for i in infra))
    ctx.check("conflict-not-silently-resolved", bool(eng) and bool(infra))
