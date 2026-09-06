"""Family F — Forgetting. Catches zombie memory: replaced or retracted items
still shown, or returning. See MEASURES.md § F."""

from bench.scenario import Ctx, scenario


@scenario("F0", "F")
def f0(ctx: Ctx) -> None:
    """Notes are retractable, and the retraction is announced. Correction is
    not decay: an item that was false may have been acted on, and a reader
    cannot revise what it is never handed."""
    g = ctx.standard()
    a = ctx.agent(g["support"])
    r = ctx.write(a, "note")
    ctx.admitted(a, "note")
    ctx.retract(a, r.id)
    read = ctx.read(a)
    ctx.absent(read, ctx.canary("note"), "note-removed")
    ctx.check("retraction-announced", bool(ctx.events_for(read, ctx.canary("note"))))


@scenario("F1", "F")
def f1(ctx: Ctx) -> None:
    """A replaced item leaves and stays gone."""
    g = ctx.standard()
    a = ctx.agent(g["billing"])
    subj = f"batch-{ctx.variant}"
    first = ctx.write(a, "old", subject=subj)
    ctx.admitted(a, "old")
    ctx.write(a, "new", subject=subj, replaces=first.id)
    for n in range(5):
        ctx.write(a, f"noise{n}")
    read = ctx.read(a)
    ctx.absent(read, ctx.canary("old"), "replaced-stays-gone")


@scenario("F2", "F")
def f2(ctx: Ctx) -> None:
    """A retracted item is shown only as its withdrawal event, never as
    current memory."""
    g = ctx.standard()
    a = ctx.agent(g["billing"])
    r = ctx.write(a, "claim")
    ctx.admitted(a, "claim")
    ctx.retract(a, r.id)
    read = ctx.read(a)
    ctx.absent(read, ctx.canary("claim"), "not-current")


@scenario("F3", "F")
def f3(ctx: Ctx) -> None:
    """No resurrection: neither a replaced nor a retracted item returns as
    writing continues."""
    g = ctx.standard()
    a = ctx.agent(g["billing"])
    subj = f"cursor-{ctx.variant}"
    first = ctx.write(a, "old", subject=subj)
    ctx.admitted(a, "old", "replaced-was-admitted")
    ctx.write(a, "new", subject=subj, replaces=first.id)
    gone = ctx.write(a, "retracted")
    ctx.admitted(a, "retracted", "retracted-was-admitted")
    ctx.retract(a, gone.id)
    for n in range(10):
        ctx.write(a, f"noise{n}")
    read = ctx.read(a)
    ctx.absent(read, ctx.canary("old"), "replaced-not-back")
    ctx.absent(read, ctx.canary("retracted"), "retracted-not-back")
