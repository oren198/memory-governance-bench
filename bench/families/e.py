"""Family E — Echo. Catches echo chambers: a restatement counted as a second
source, an attribution outliving its source's retraction. See MEASURES.md § E."""

from bench.scenario import Ctx, scenario


def _echo_world(ctx: Ctx) -> dict[str, str]:
    """Tier-2 hears Billing directly and is also part of Support, so a claim
    can reach it twice: once first-hand, once as Support's restatement."""
    v = ctx.variant
    g = {
        "billing": f"billing_{v}",
        "support": f"support_{v}",
        "tier2": f"tier2_{v}",
        "company": f"company_{v}",
    }
    ctx.build(
        roles={gid: role for role, gid in g.items()},
        groups=g.values(),
        part_of=[(g["support"], g["company"]), (g["billing"], g["company"]),
                 (g["tier2"], g["support"])],
        listens_to=[(g["support"], g["billing"]), (g["tier2"], g["billing"])],
    )
    return g


@scenario("E1", "E")
def e1(ctx: Ctx) -> None:
    """A restatement is not a second source. The same claim, first-hand and
    restated, is never shown as two independent claims."""
    g = _echo_world(ctx)
    claim = ctx.text("claim", words=14, group=g["billing"])
    r = ctx.write(ctx.agent(g["billing"]), "claim", content=claim)
    ctx.announce(ctx.agent(g["billing"]), r.id)
    restated = f"According to {g['billing']}, {claim}"
    ctx.write(ctx.agent(g["support"]), None, content=restated)
    read = ctx.read(ctx.agent(g["tier2"]))
    shown = ctx.items_with(read, ctx.canary("claim"))
    independent = [i for i in shown if i.attributed_to is None and i.via is None]
    ctx.check(
        "not-two-independent-claims",
        len(independent) <= 1,
        independent=[i.origin for i in independent],
        total=len(shown),
    )


@scenario("E2", "E")
def e2(ctx: Ctx) -> None:
    """Attribution is live. After the source retracts, nothing is still
    attributed to it."""
    g = _echo_world(ctx)
    claim = ctx.text("claim", words=14, group=g["billing"])
    r = ctx.write(ctx.agent(g["billing"]), "claim", content=claim)
    ctx.announce(ctx.agent(g["billing"]), r.id)
    ctx.write(ctx.agent(g["support"]), None, content=f"According to {g['billing']}, {claim}")
    ctx.read(ctx.agent(g["support"]))
    ctx.retract(ctx.agent(g["billing"]), r.id)
    read = ctx.read(ctx.agent(g["support"]))
    stale = [i for i in ctx.items_with(read, ctx.canary("claim"))
             if i.attributed_to == g["billing"]]
    ctx.check("no-stale-attribution", not stale, stale=len(stale))


@scenario("E3", "E")
def e3(ctx: Ctx) -> None:
    """No laundering after retraction. If the claim survives its source's
    retraction it stands on the restater's own authority — its own origin,
    no borrowed attribution — never the source's copy with the label off."""
    g = _echo_world(ctx)
    claim = ctx.text("claim", words=14, group=g["billing"])
    r = ctx.write(ctx.agent(g["billing"]), "claim", content=claim)
    ctx.announce(ctx.agent(g["billing"]), r.id)
    ctx.write(ctx.agent(g["support"]), None, content=f"According to {g['billing']}, {claim}")
    ctx.retract(ctx.agent(g["billing"]), r.id)
    read = ctx.read(ctx.agent(g["support"]))
    surviving = ctx.items_with(read, ctx.canary("claim"))
    laundered = [i for i in surviving if i.origin == g["billing"]]
    ctx.check("no-source-copy-survives", not laundered, count=len(laundered))
    ctx.check(
        "survivor-stands-on-its-own",
        all(i.origin == g["support"] and i.attributed_to is None for i in surviving),
        origins=[i.origin for i in surviving],
    )


@scenario("E4", "E")
def e4(ctx: Ctx) -> None:
    """Mutual listening terminates. Two groups that listen to each other do
    not circulate one claim as many, and it never returns to its source as
    something new."""
    v = ctx.variant
    g = {"billing": f"billing_{v}", "support": f"support_{v}", "company": f"company_{v}"}
    ctx.build(
        roles={gid: role for role, gid in g.items()},
        groups=g.values(),
        part_of=[(g["billing"], g["company"]), (g["support"], g["company"])],
        listens_to=[(g["support"], g["billing"]), (g["billing"], g["support"])],
    )
    claim = ctx.text("claim", words=14, group=g["billing"])
    r = ctx.write(ctx.agent(g["billing"]), "claim", content=claim)
    ctx.announce(ctx.agent(g["billing"]), r.id)
    heard = ctx.read(ctx.agent(g["support"]))
    relayed = ctx.items_with(heard, ctx.canary("claim"))
    if relayed and relayed[0].receipt:
        ctx.announce(ctx.agent(g["support"]), relayed[0].receipt)
    support_read = ctx.read(ctx.agent(g["support"]))
    billing_read = ctx.read(ctx.agent(g["billing"]))
    ctx.check("shown-once-to-listener",
              len(ctx.items_with(support_read, ctx.canary("claim"))) <= 1)
    back = [i for i in ctx.items_with(billing_read, ctx.canary("claim"))
            if i.origin != g["billing"]]
    ctx.check("does-not-return-as-new", not back, foreign=[i.origin for i in back])
