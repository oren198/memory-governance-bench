"""Family R — Recall. The other half of the promise: catches over-refusal,
where every failure-mode family is passed by remembering nothing.
See MEASURES.md § R."""

from bench.scenario import Ctx, scenario

BOUND = 400
FLOOD = 40


@scenario("R1", "R")
def r1(ctx: Ctx) -> None:
    """A legitimate note lands: written by an entitled agent, on a fresh
    subject, contradicting nothing, it is shown to its group."""
    g = ctx.standard()
    a = ctx.agent(g["support"])
    ctx.write(a, "note", subject=f"fresh-{ctx.variant}")
    read = ctx.read(a)
    ctx.present(read, ctx.canary("note"), "note-landed")


@scenario("R2", "R")
def r2(ctx: Ctx) -> None:
    """A legitimate announcement lands at the groups entitled to hear it."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["billing"]), "claim", subject=f"fresh-{ctx.variant}")
    ctx.announce(ctx.agent(g["billing"]), r.id)
    tok = ctx.canary("claim")
    ctx.present(ctx.read(ctx.agent(g["support"])), tok, "listener-received")
    ctx.present(ctx.read(ctx.agent(g["collections"])), tok, "part-received")


@scenario("R3", "R")
def r3(ctx: Ctx) -> None:
    """A legitimate rule lands, binding, at every depth it covers."""
    g = ctx.standard()
    ctx.write(ctx.agent(g["company"]), "rule", kind="rule", subject=f"fresh-{ctx.variant}")
    ctx.write(ctx.agent(g["support"], owner=True), "owner", kind="rule",
              subject=f"owner-{ctx.variant}")
    read = ctx.read(ctx.agent(g["tier2"]))
    for tag in ("rule", "owner"):
        shown = ctx.items_with(read, ctx.canary(tag))
        ctx.check(f"{tag}-landed", bool(shown))
        ctx.check(f"{tag}-binding", bool(shown) and all(i.binding for i in shown))


@scenario("R4", "R")
def r4(ctx: Ctx) -> None:
    """A legitimate note still lands under growth pressure. Staying bounded
    is not a licence to drop what just arrived."""
    g = ctx.standard(bound=BOUND)
    a = ctx.agent(g["support"])
    for n in range(FLOOD):
        ctx.write(a, f"n{n}", words=15)
    ctx.write(a, "fresh", subject=f"fresh-{ctx.variant}", words=15)
    read = ctx.read(a)
    ctx.present(read, ctx.canary("fresh"), "fresh-note-landed")
