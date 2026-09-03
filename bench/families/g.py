"""Family G — Growth. Catches unbounded growth and silent loss: reads over
their bound, rules lost to condensation, drops nobody was told about.
See MEASURES.md § G."""

from bench.scenario import Ctx, scenario

BOUND = 400
FLOOD = 60


@scenario("G1", "G")
def g1(ctx: Ctx) -> None:
    """Reads stay within the bound, counted by the benchmark rather than
    reported by the system."""
    g = ctx.standard(bound=BOUND)
    a = ctx.agent(g["support"])
    for n in range(FLOOD):
        ctx.write(a, f"n{n}", words=15)
    read = ctx.read(a)
    ctx.check("within-bound", ctx.words_of(read) <= BOUND,
              words=ctx.words_of(read), bound=BOUND)


@scenario("G2", "G")
def g2(ctx: Ctx) -> None:
    """Rules survive condensation. Notes may be dropped to stay bounded;
    a binding rule may not."""
    g = ctx.standard(bound=BOUND)
    ctx.write(ctx.agent(g["support"], owner=True), "rule", kind="rule", words=15)
    a = ctx.agent(g["support"])
    for n in range(FLOOD):
        ctx.write(a, f"n{n}", words=15)
    read = ctx.read(a)
    shown = ctx.items_with(read, ctx.canary("rule"))
    ctx.check("rule-survives", bool(shown))
    ctx.check("rule-still-binding", bool(shown) and all(i.binding for i in shown))


@scenario("G3", "G")
def g3(ctx: Ctx) -> None:
    """Drops are discoverable. If material was condensed away, the reader is
    told that it was — a fleet that forgets silently cannot know what it no
    longer knows."""
    g = ctx.standard(bound=BOUND)
    a = ctx.agent(g["support"])
    for n in range(FLOOD):
        ctx.write(a, f"n{n}", words=15)
    read = ctx.read(a)
    missing = [n for n in range(FLOOD) if not ctx.shows(read, ctx.canary(f"n{n}"))]
    if not missing:
        ctx.check("nothing-dropped-nothing-owed", True, dropped=0)
        return
    ctx.check("drop-reported", read.dropped is not None and read.dropped > 0,
              missing=len(missing), reported=read.dropped)


@scenario("G4", "G")
def g4(ctx: Ctx) -> None:
    """Repeats collapse: the same claim written many times is shown once."""
    g = ctx.standard(bound=BOUND)
    a = ctx.agent(g["support"])
    content = ctx.text("dup", words=15)
    subj = f"dup-{ctx.variant}"
    for _ in range(8):
        ctx.write(a, "dup", content=content, subject=subj)
    read = ctx.read(a)
    shown = ctx.items_with(read, ctx.canary("dup"))
    ctx.check("shown-once", len(shown) <= 1, count=len(shown))
