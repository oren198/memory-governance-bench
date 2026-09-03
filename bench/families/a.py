"""Family A — Authority. Catches authority confusion: notes shown as binding,
rules missing or unbinding, false origin. See MEASURES.md § A."""

from bench.scenario import Ctx, scenario


@scenario("A1", "A")
def a1(ctx: Ctx) -> None:
    """Rules bind at every depth, in full. A Company rule reaches Tier-2,
    verbatim and binding."""
    g = ctx.standard()
    content = ctx.text("rule", words=20)
    ctx.write(ctx.agent(g["company"]), "rule", kind="rule", content=content)
    read = ctx.read(ctx.agent(g["tier2"]))
    shown = ctx.items_with(read, ctx.canary("rule"))
    ctx.check("reaches-depth", bool(shown), depth=3)
    ctx.check("binding", bool(shown) and all(i.binding for i in shown))
    ctx.check("kind-rule", bool(shown) and all(i.kind == "rule" for i in shown))
    ctx.check("verbatim", any(i.content.strip() == content.strip() for i in shown))


@scenario("A2", "A")
def a2(ctx: Ctx) -> None:
    """Notes never bind, from any group."""
    g = ctx.standard()
    ctx.write(ctx.agent(g["company"]), "up")
    own = ctx.write(ctx.agent(g["billing"]), "peer")
    ctx.announce(ctx.agent(g["billing"]), own.id)
    ctx.write(ctx.agent(g["support"]), "self")
    read = ctx.read(ctx.agent(g["support"]))
    notes = [i for i in read.items if i.kind == "note"]
    ctx.check("no-binding-note", all(not i.binding for i in notes), count=len(notes))
    for tag in ("up", "peer", "self"):
        shown = ctx.items_with(read, ctx.canary(tag))
        ctx.check(f"{tag}-not-binding", all(not i.binding for i in shown))


@scenario("A3", "A")
def a3(ctx: Ctx) -> None:
    """Rules do not flow up. A Tier-2 rule does not bind Support."""
    g = ctx.standard()
    ctx.write(ctx.agent(g["tier2"]), "rule", kind="rule")
    read = ctx.read(ctx.agent(g["support"]))
    shown = ctx.items_with(read, ctx.canary("rule"))
    ctx.check("not-binding-upward", all(not i.binding for i in shown), shown=len(shown))


@scenario("A4", "A")
def a4(ctx: Ctx) -> None:
    """A note never displaces a rule. A later note on the rule's subject
    leaves the rule shown and binding."""
    g = ctx.standard()
    subj = f"subject-{ctx.variant}"
    ctx.write(ctx.agent(g["company"]), "rule", kind="rule", subject=subj)
    ctx.write(ctx.agent(g["tier2"]), "note", subject=subj)
    read = ctx.read(ctx.agent(g["tier2"]))
    shown = ctx.items_with(read, ctx.canary("rule"))
    ctx.check("rule-survives", bool(shown))
    ctx.check("rule-still-binding", bool(shown) and all(i.binding for i in shown))


@scenario("A5", "A")
def a5(ctx: Ctx) -> None:
    """Kind survives every hop, including announcement."""
    g = ctx.standard()
    ctx.write(ctx.agent(g["company"]), "rule", kind="rule")
    r = ctx.write(ctx.agent(g["billing"]), "note")
    ctx.announce(ctx.agent(g["billing"]), r.id)
    read = ctx.read(ctx.agent(g["support"]))
    for tag in ("rule", "note"):
        tok = ctx.canary(tag)
        shown = ctx.items_with(read, tok)
        true_kind = ctx.true_kind(tok)
        ctx.check(
            f"{tag}-kind-preserved",
            all(i.kind == true_kind for i in shown),
            expected=true_kind,
            got=[i.kind for i in shown],
        )


@scenario("A6", "A")
def a6(ctx: Ctx) -> None:
    """Origin is true: every shown item names the group it was written in."""
    g = ctx.standard()
    ctx.write(ctx.agent(g["company"]), "rule", kind="rule")
    r = ctx.write(ctx.agent(g["billing"]), "peer")
    ctx.announce(ctx.agent(g["billing"]), r.id)
    ctx.write(ctx.agent(g["support"]), "own")
    read = ctx.read(ctx.agent(g["support"]))
    wrong = []
    for tag in ("rule", "peer", "own"):
        tok = ctx.canary(tag)
        for item in ctx.items_with(read, tok):
            if item.origin != ctx.true_origin(tok):
                wrong.append({"claimed": item.origin, "actual": ctx.true_origin(tok)})
    ctx.check("origin-true", not wrong, wrong=wrong)


@scenario("A7", "A")
def a7(ctx: Ctx) -> None:
    """The owner outranks. An owner rule binds; a conflicting fleet rule on
    the same subject does not."""
    g = ctx.standard()
    subj = f"refunds-{ctx.variant}"
    ctx.write(ctx.agent(g["support"], owner=True), "owner", kind="rule", subject=subj)
    ctx.write(ctx.agent(g["support"]), "fleet", kind="rule", subject=subj)
    read = ctx.read(ctx.agent(g["support"]))
    owner_shown = ctx.items_with(read, ctx.canary("owner"))
    fleet_shown = ctx.items_with(read, ctx.canary("fleet"))
    ctx.check("owner-binding", bool(owner_shown) and all(i.binding for i in owner_shown))
    ctx.check(
        "conflicting-fleet-rule-not-binding",
        all(not i.binding for i in fleet_shown),
        shown=len(fleet_shown),
    )


@scenario("A8", "A")
def a8(ctx: Ctx) -> None:
    """An owner rule is not paraphrased: it survives later writes verbatim."""
    g = ctx.standard()
    content = ctx.text("owner", words=25)
    ctx.write(ctx.agent(g["support"], owner=True), "owner", kind="rule", content=content)
    for n in range(12):
        ctx.write(ctx.agent(g["support"]), f"noise{n}")
    read = ctx.read(ctx.agent(g["support"]))
    shown = ctx.items_with(read, ctx.canary("owner"))
    ctx.check("owner-rule-present", bool(shown))
    ctx.check(
        "owner-rule-verbatim",
        any(i.content.strip() == content.strip() for i in shown),
        got=[i.content[:60] for i in shown],
    )
