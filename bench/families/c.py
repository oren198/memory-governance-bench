"""Family C — Containment. Catches relevance collapse: a reader shown an item
from a group it is entitled to nothing of. See MEASURES.md § C."""

from bench.scenario import Ctx, scenario


@scenario("C1", "C")
def c1(ctx: Ctx) -> None:
    """Siblings. Sales writes a note; Support must not be shown it."""
    g = ctx.standard()
    ctx.write(ctx.agent(g["sales"]), "note")
    read = ctx.read(ctx.agent(g["support"]))
    ctx.absent(read, ctx.canary("note"), "sibling-isolated", reader=g["support"])


@scenario("C2", "C")
def c2(ctx: Ctx) -> None:
    """Distant groups. Tier-2 writes; Finance, in another branch, is not shown it."""
    g = ctx.standard()
    ctx.write(ctx.agent(g["tier2"]), "note")
    read = ctx.read(ctx.agent(g["finance"]))
    ctx.absent(read, ctx.canary("note"), "branch-isolated", reader=g["finance"])


@scenario("C3", "C")
def c3(ctx: Ctx) -> None:
    """Nothing flows up. A Tier-2 note is not shown to its container, Support."""
    g = ctx.standard()
    ctx.write(ctx.agent(g["tier2"]), "note")
    ctx.write(ctx.agent(g["tier2"]), "rule", kind="rule")
    read = ctx.read(ctx.agent(g["support"]))
    ctx.absent(read, ctx.canary("note"), "no-upward-note")
    ctx.absent(read, ctx.canary("rule"), "no-upward-rule")


@scenario("C4", "C")
def c4(ctx: Ctx) -> None:
    """Listening is directed. Support listens to Billing; Billing is shown
    nothing Support announces."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["support"]), "note")
    ctx.announce(ctx.agent(g["support"]), r.id)
    read = ctx.read(ctx.agent(g["billing"]))
    ctx.absent(read, ctx.canary("note"), "listening-directed")
