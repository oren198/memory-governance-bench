"""Family S — Announcement & retraction. Catches silent drift: announcements
reaching the wrong readers or misrepresenting their group, retractions that
remove without telling anyone. See MEASURES.md § S."""

from bench.scenario import Ctx, scenario


@scenario("S1", "S")
def s1(ctx: Ctx) -> None:
    """An announcement reaches the groups that listen to the announcer and
    the groups that are part of it, named as the announcer's."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["billing"]), "claim")
    ctx.announce(ctx.agent(g["billing"]), r.id)
    tok = ctx.canary("claim")
    for reader in ("support", "collections"):
        read = ctx.read(ctx.agent(g[reader]))
        shown = ctx.items_with(read, tok)
        ctx.check(f"{reader}-shown", bool(shown), reader=g[reader])
        ctx.check(f"{reader}-origin", all(i.origin == g["billing"] for i in shown),
                  got=[i.origin for i in shown])


@scenario("S2", "S")
def s2(ctx: Ctx) -> None:
    """An announcement reaches nobody else: not siblings, not the container."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["billing"]), "claim")
    ctx.announce(ctx.agent(g["billing"]), r.id)
    tok = ctx.canary("claim")
    for reader in ("sales", "company", "tier2"):
        read = ctx.read(ctx.agent(g[reader]))
        ctx.absent(read, tok, f"{reader}-not-shown", reader=g[reader])


@scenario("S3", "S")
def s3(ctx: Ctx) -> None:
    """Only held items are announced. Announcing something retracted is
    refused, or at least never delivered."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["billing"]), "claim")
    ctx.retract(ctx.agent(g["billing"]), r.id)
    result = ctx.announce(ctx.agent(g["billing"]), r.id)
    read = ctx.read(ctx.agent(g["support"]))
    delivered = ctx.items_with(read, ctx.canary("claim"))
    ctx.check("refused-or-undelivered", (not result.accepted) or (not delivered),
              accepted=result.accepted, delivered=len(delivered))


@scenario("S4a", "S")
def s4a(ctx: Ctx) -> None:
    """A retraction removes: the claim stops being shown as current."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["billing"]), "claim")
    ctx.announce(ctx.agent(g["billing"]), r.id)
    ctx.read(ctx.agent(g["support"]))
    ctx.retract(ctx.agent(g["billing"]), r.id)
    read = ctx.read(ctx.agent(g["support"]))
    ctx.absent(read, ctx.canary("claim"), "removed")


@scenario("S4b", "S")
def s4b(ctx: Ctx) -> None:
    """A retraction notifies. Absence is not information: the reader is shown
    a withdrawal event identifying what was pulled."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["billing"]), "claim")
    ctx.announce(ctx.agent(g["billing"]), r.id)
    ctx.read(ctx.agent(g["support"]))
    ctx.retract(ctx.agent(g["billing"]), r.id)
    read = ctx.read(ctx.agent(g["support"]))
    events = ctx.events_for(read, ctx.canary("claim"))
    ctx.check("withdrawal-delivered", bool(events), events=len(events))


@scenario("S5", "S")
def s5(ctx: Ctx) -> None:
    """A retraction follows the relay: it reaches readers who heard the claim
    second-hand, not only the announcer's direct listeners."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["billing"]), "claim")
    ctx.announce(ctx.agent(g["billing"]), r.id)
    heard = ctx.read(ctx.agent(g["support"]))
    relayed = ctx.items_with(heard, ctx.canary("claim"))
    ctx.check("support-heard-it", bool(relayed))
    if not (relayed and relayed[0].receipt):
        ctx.check("relayable", False, why="no receipt on the received item")
        return
    ctx.announce(ctx.agent(g["support"]), relayed[0].receipt)
    ctx.read(ctx.agent(g["tier2"]))
    ctx.retract(ctx.agent(g["billing"]), r.id)
    read = ctx.read(ctx.agent(g["tier2"]))
    ctx.absent(read, ctx.canary("claim"), "second-hand-removed")
    ctx.check("second-hand-notified", bool(ctx.events_for(read, ctx.canary("claim"))))


@scenario("S6", "S")
def s6(ctx: Ctx) -> None:
    """Second-hand material is labelled: the origin is the group that wrote
    it, and the relayer is named."""
    g = ctx.standard()
    r = ctx.write(ctx.agent(g["billing"]), "claim")
    ctx.announce(ctx.agent(g["billing"]), r.id)
    heard = ctx.read(ctx.agent(g["support"]))
    relayed = ctx.items_with(heard, ctx.canary("claim"))
    if not (relayed and relayed[0].receipt):
        ctx.check("relayable", False, why="no receipt on the received item")
        return
    ctx.announce(ctx.agent(g["support"]), relayed[0].receipt)
    read = ctx.read(ctx.agent(g["tier2"]))
    shown = ctx.items_with(read, ctx.canary("claim"))
    ctx.check("shown-second-hand", bool(shown))
    ctx.check("origin-is-author", all(i.origin == g["billing"] for i in shown),
              got=[i.origin for i in shown])
    ctx.check("via-names-relayer", all(i.via == g["support"] for i in shown),
              got=[i.via for i in shown])


@scenario("S7", "S")
def s7(ctx: Ctx) -> None:
    """A retraction reaches the absorber, not just the relayer. Support does
    not forward Billing's claim — it believes it and writes it in its own
    words, citing Billing. When Billing retracts, Support must learn."""
    g = ctx.standard()
    claim = ctx.text("claim", words=14, group=g["billing"])
    r = ctx.write(ctx.agent(g["billing"]), "claim", content=claim)
    ctx.announce(ctx.agent(g["billing"]), r.id)
    ctx.read(ctx.agent(g["support"]))
    ctx.write(ctx.agent(g["support"]), None,
              content=f"According to {g['billing']}, {claim} Plan the batch size around it.")
    ctx.retract(ctx.agent(g["billing"]), r.id)
    read = ctx.read(ctx.agent(g["support"]))
    tok = ctx.canary("claim")
    ctx.check("absorber-notified", bool(ctx.events_for(read, tok)))
    stale = [i for i in ctx.items_with(read, tok) if i.attributed_to == g["billing"]]
    ctx.check("no-dead-attribution", not stale, stale=len(stale))
