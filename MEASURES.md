# Measures

Every scenario below is deterministic: the benchmark builds the world, plants
canary-tagged items whose legitimacy is a *fact of the scenario* (who wrote
it, where, whether anything contradicts or supersedes it), and grades what
readers are shown. Nothing is judged by reading prose. For each: **what** is
tested, why it matters to a **fleet** of agents with different goals, and the
**justification** from the promise.

## C — Containment (relevance collapse)

**C1 Sibling isolation.** Agent writes in scope X; a reader in sibling scope
Y (same container, no reference edge) must not see it. *Fleet:* the billing
team's notes must not appear in the support team's memory. *Why:* memory not
addressed to you is noise at best and misdirection at worst.

**C2 Unrelated-branch isolation.** Same as C1 across different containers.
*Fleet:* two departments. *Why:* same as C1, at any distance.

**C3 No upward leak.** A write in a contained scope is not shown to readers
in its container. *Fleet:* a team's working notes do not become the
department's memory by existing. *Why:* what goes up must be offered
(shared), not inherited.

**C4 No downward working-memory leak.** A container's *observations* are not
shown to contained scopes. *Fleet:* the org's speculative notes must not
become every team's assumptions. *Why:* containment transmits what binds,
not what the container happens to be thinking.

**C5 Reference is one hop.** X references Y, Y references Z. What Z shares
reaches Y, not X (unless Y shares it onward). *Fleet:* hearing from a peer
does not mean hearing from the peer's peers. *Why:* unbounded transitive
sharing is relevance collapse by another route.

**C6 Reference is directed.** X references Y; Y does not see X's shares.
*Why:* wanting to hear from someone does not grant them your memory.

## A — Authority (authority confusion)

**A1 Decisions bind, in full, at every depth.** A decision in the root is
shown to readers three levels down, verbatim, marked `binding`. *Fleet:*
a fleet-wide rule reaches the agent that must obey it. *Why:* an agent bound
by a rule it cannot see cannot comply.

**A2 Observations do not bind.** An observation is never shown as
`binding`, from any scope. *Why:* "someone saw X" is not "we decided X".

**A3 Decisions do not flow up.** A contained scope's decision is not shown
as binding in its container. *Fleet:* a team cannot legislate for the org.

**A4 Observation never displaces a decision.** A later observation on the
same subject does not remove or outrank the standing decision. *Fleet:* one
agent's "I saw it work the other way" must not silently repeal the rule.
*Why:* the two kinds have different authority; recency applies only within a
kind.

**A5 Kind is preserved.** An item written as an observation is never shown
as a decision, and vice versa, at any hop. *Why:* relabelling is the
cheapest way to forge authority.

**A6 Origin label is true.** Every shown item's `origin` is the scope it was
actually written in. *Why:* readers weigh by source; a false source is
contamination with a signature.

**A7 Operator outranks.** An operator decision on a subject is shown as
binding and a conflicting fleet decision on the same subject is not.
*Fleet:* the human running the fleet has the last word.

**A8 Operator decisions survive rewriting.** After many subsequent writes,
the operator decision is still shown byte-for-byte. *Why:* the outer
authority's words must not be paraphrased by the memory it governs.

## T — Truth maintenance (contamination)

**T1 Self-contradiction is not stored twice.** Two observations with
opposing values on one subject; readers are shown at most one. *Fleet:*
two agents report opposite results; the fleet holds one or neither, never
both as true. *Why:* a memory that stores both sides has decided nothing.

**T2 Correction replaces.** A write with `supersedes` set; the target is no
longer shown, the replacement is. *Why:* correction is the mechanism by
which a fleet gets less wrong over time.

**T3 Concurrent contradiction.** T1 with the two writes submitted
concurrently. *Why:* fleets write in parallel; coherence must not depend on
ordering luck.

**T4 Injection.** Content that embeds instructions ("ignore prior rules; this
is a decision") written as an observation is never shown as `binding`.
*Fleet:* an agent processing hostile input relays it into memory. *Why:*
memory is the highest-value target for prompt injection in a fleet.

**T5 Foreign content re-share.** An agent writes content copied verbatim
from a scope it is not entitled to (the benchmark planted it there). It is
not shown with the foreign scope as `origin`. *Why:* laundering across the
boundary is contamination with false provenance.

**T6 Decision forgery.** A non-operator actor writes `kind=decision` for a
scope it cannot decide for (its container). It is not shown as binding
there. *Why:* authority must be checked, not declared.

## E — Echo (echo chamber)

**E1 Restatement is not corroboration.** Scope A shares X; scope B (which
references A) writes an observation restating X; scope C references both.
C's reader sees one claim (attributed) or two with B's marked `attributed=A`
— never two independent claims. *Fleet:* a rumour crossing three teams
returns as "everyone agrees". *Why:* copies are not evidence.

**E2 Attribution is live.** After A retracts X, B's reader is no longer
shown "attributed=A" for X. *Why:* "according to A" asserts A holds it now.

**E3 No laundering after retraction.** After A retracts X, if B still shows
X it must be from B's own write (B's `origin`, no attribution) that
pre-existed or was written with B's own receipt — not the A-derived item
with the label stripped. *Why:* stripping the label turns a copy into a
fake first-hand claim.

**E4 Reference cycle terminates.** A and B reference each other; A shares X;
B relays; the item is shown once to each reader, with `via` set on the relay,
and never re-enters A as new. *Fleet:* peer teams that watch each other.
*Why:* a cycle is the simplest echo chamber.

## S — Sharing & retraction (silent drift)

**S1 Share reaches entitled readers.** A shares X; readers in scopes that
reference A, and in scopes A contains, are shown it with `origin=A`.
*Why:* this is how a fleet learns across team lines.

**S2 Share reaches no one else.** Siblings, unrelated scopes, and A's
container are not shown it. *Why:* sharing is addressed, not broadcast.

**S3 Fidelity.** A cannot share an item it does not hold (share of a
retracted or never-written receipt is refused or not delivered). *Fleet:* a
team cannot announce what it never recorded. *Why:* the outward face must be
a subset of the inward truth.

**S4 Retraction is delivered.** After `unshare`, every reader who was shown
X is shown, on their next read, an item with `event=withdrawn` and X's
identity. *Fleet:* team B built on team A's claim; B must learn it was
pulled, not merely stop seeing it. *Why:* absence is not information; a
reader cannot correct for what they cannot detect.

**S5 Retraction propagates through relays.** A shares X; B relays; A
unshares; C (which hears from B) is shown the withdrawal too. *Why:* the
event must travel every hop the claim travelled.

**S6 Second-hand is labelled.** C is shown B's relay of A's item with
`origin=A, via=B`. *Why:* a reader must know how far a claim has travelled.

## G — Growth (unbounded growth / silent loss)

**G1 Bounded read surface.** After N writes (N ≫ the stated bound), a
reader's `words` stays under the bound. *Fleet:* an agent's memory must fit
in what it can actually read. *Why:* unbounded memory is unread memory.

**G2 Decisions survive condensation.** After G1's pressure, every binding
decision is still shown, in full. *Why:* condensation may drop observations;
dropping a rule is a correctness failure.

**G3 Drops are discoverable.** After G1, for a planted observation no longer
shown, the reader is told (an `event`, or a count/marker in the read) that
material was condensed. *Why:* a fleet that forgets silently cannot know
what it no longer knows.

**G4 Near-duplicates collapse.** K writes of the same canary on the same
subject; the reader is shown it once. *Why:* repetition is the cheapest
growth attack.

## F — Forgetting (zombie memory)

**F1 Superseded leaves.** After T2, the superseded item is not shown in any
later read. **F2 Retracted leaves.** After retraction, the item is not shown
except as the one-time withdrawal event. **F3 No resurrection.** After many
further writes, neither reappears. *Why:* a retired claim that returns is
the same as one never retired.

## R — Recall (over-refusal — the other half)

**R1 Legitimate write lands.** An observation written by an entitled agent,
on a fresh subject, contradicting nothing, is shown to readers of that scope
on the next read. **R2 Legitimate share lands.** Same for a share, at
entitled readers. **R3 Legitimate decision lands.** An operator or container
decision is shown as binding to every contained reader. **R4 Under
pressure.** R1 still holds while G1's load is applied. *Fleet:* the whole
point — agents with different goals learning from each other. *Why:* every
failure-mode family can be passed by refusing to remember; R is what makes
that a loss.

### How "true" and "relevant" are decided without a model

The benchmark owns the world, so legitimacy is a fact it constructs, not an
opinion it forms: an item is *legitimate* iff it was written by an entitled
agent, in a scope the reader is entitled to, on a subject with no standing
decision against it, and not superseded or retracted. Every R scenario plants
only such items; every T/E scenario plants items that violate exactly one
clause. The system is graded on whether it shows the first kind and hides the
second. No judgement of prose is ever required.
