# The model

This file defines every word the benchmark uses. Nothing else in the
repository introduces a term. If a word is not defined here, a measure may
not use it.

The model describes a **fleet** and its **memory** as an outside observer
would: who exists, what they can do, and what they are shown. It says
nothing about how a memory system is built.

## A worked example, first

A company runs a fleet of AI agents. There is a **Sales** group, a
**Support** group, and inside Support a **Tier-2** group that handles
escalations. There is also a **Billing** group. The Support agents want to
know what Billing learns about refunds, so Support *listens to* Billing.
Above them all, the company itself is a group — call it **Company** — that
Sales, Support and Billing are all *part of*. A human, the fleet's
**owner**, can set rules for any group.

- A Tier-2 agent notices "refund requests over $500 need a manager
  signature". That is a **note**: something it saw. It writes it to Tier-2's
  memory.
- The Support lead decides "always answer refund tickets within 4 hours".
  That is a **rule**: it binds every agent in Support and, because Tier-2 is
  part of Support, every Tier-2 agent too.
- Billing writes a note "the refund API times out above 200 items" and
  **announces** it. Because Support listens to Billing, Support agents are
  now shown it — labelled as Billing's.
- Sales agents are shown none of the above. Nothing makes Sales entitled to
  Support's or Billing's memory.
- Later Billing finds the timeout was a fluke and **retracts** the
  announcement. Every Support agent who was shown it must now be told it was
  withdrawn — not simply stop seeing it.

Everything the benchmark measures is a variation on this story.

## Definitions

### The fleet

**Agent.** Anything that writes to or reads from the memory. Agents differ
in goal and role; that is what makes it a fleet rather than one program with
many copies.

**Group.** A set of agents that share one memory. Every agent acts *from*
exactly one group at a time. A group is the unit of entitlement: an agent
is shown its group's memory and nothing else, except through the two
relations below.

**Part of.** Group A may be *part of* group B (Tier-2 is part of Support).
Then B's rules bind A's agents. Nothing else passes from B to A by virtue of
this relation; in particular B's notes do not. Nothing passes from A up to B.
"Part of" is transitive: Tier-2 is part of Company because Support is.

**Listens to.** Group A may *listen to* group B (Support listens to Billing).
Then B's announcements are shown to A's agents. The relation is directed:
Billing is shown nothing of Support's. It is not transitive: if Billing
listens to Finance, Support is not thereby shown Finance's announcements.
Two groups may listen to each other.

**Owner.** A human or process outside the fleet who may write rules for any
group. An owner's rule outranks any rule the fleet writes for itself.

### Memory items

**Note.** Something an agent observed. A note *informs* the agents who are
shown it and binds nobody.

**Rule.** Something an authority settled. A rule *binds* every agent in the
group it was written for and in every group that is part of that group, at
any depth. Only an agent acting from a group, or the owner, may write a rule
for that group; nobody may write a rule for a group they are not in.

**Subject.** An optional label on an item naming what it is about. Two items
on the same subject with incompatible content **contradict**. The benchmark
constructs contradictions by subject; it never infers them from text.

**Legitimate.** An item is legitimate for a reader when all four hold: it
was written by an agent entitled to write it; the reader is entitled to be
shown it; no rule on its subject stands against it; it has not been replaced
or retracted. Legitimacy is a fact the benchmark knows by construction — it
built the world — never an opinion formed by reading the item.

### Actions

**Write.** An agent puts a note or rule into its group's memory. A write may
name an earlier item it **replaces**.

**Announce.** An agent offers an item its group holds to the groups that
listen to its group and to the groups that are part of its group. An
announcement can only be of something the group actually holds.

**Retract.** An agent takes back a write or an announcement its group made.

**Read.** An agent asks what it is shown, acting from its group. The read is
the only thing the benchmark grades.

### What a reader is shown

Each **shown item** carries:

- its **content**;
- its **kind** — note or rule — as the reader is told to treat it;
- whether it is **binding** on this reader;
- its **origin** — the group the item was written in;
- **via** — if the item reached the reader through an intermediate group's
  announcement, that group (it is **second-hand**);
- **attributed to** — if the item is a restatement of another group's
  claim, that group. An attribution is a *live* claim: it asserts the named
  group holds the item now;
- an **event** — when the reader is being told the item was **withdrawn**
  rather than shown it as current.

**Bound.** The size of what a reader is shown, measured in words, that a
scenario states the memory must stay within.

## The promise, in these words

> Every agent can write to its group's memory, and legitimate items reach
> every agent entitled to them (**contribution**) — while no agent can make
> a reader be shown an item that is not legitimate for them, mislabel an
> item's kind, origin or attribution, or hide a rule that binds them
> (**governance**).

## Glossary

| Term | One line |
|---|---|
| fleet | many agents with different goals sharing memory |
| agent | a writer/reader, acting from one group |
| group | a set of agents sharing one memory; the unit of entitlement |
| part of | A part of B ⇒ B's rules bind A; nothing else passes; transitive |
| listens to | A listens to B ⇒ B's announcements are shown to A; directed, one hop |
| owner | outside authority; its rules outrank the fleet's |
| note | something an agent saw; informs, never binds |
| rule | a settled decision; binds its group and all groups part of it |
| subject | label on an item; same subject + incompatible content = contradiction |
| legitimate | entitled writer, entitled reader, no rule against it, not replaced/retracted |
| write / replaces | put an item in; optionally supersede an earlier one |
| announce | offer a held item to listeners and parts |
| retract | take back a write or an announcement |
| read | what an agent is shown; the only graded thing |
| origin / via / attributed to | where it was written / which group relayed it / whose claim it restates |
| binding | the reader is told the item binds them |
| withdrawn | an event telling a reader an item they were shown was retracted |
| bound | the maximum size of a read, in words |

## Forced by the promise, and chosen

Not every rule in this model is forced by the promise. Being honest about
which is which is what keeps the benchmark from grading systems on one
school of thought.

**Forced.** Deny any of these and the promise fails outright:

- An agent is not shown items from groups it is entitled to nothing of.
- A rule that binds an agent is shown to that agent, in full.
- Kind, origin, `via` and `attributed to` are true as shown.
- A reader is not shown both sides of a contradiction as current.
- A reader can detect that something they were shown was retracted.
- Reads stay within their bound, and rules are never what gets dropped.
- Legitimate items reach the agents entitled to them.

**Chosen.** Defensible, but a different fleet memory could decide otherwise
and still keep the promise:

- *Notes do not flow down from a container.* A system could pass a
  container's notes to its parts as clearly-labelled, non-binding material.
- *Listening is one hop and not transitive.* A system could propagate
  announcements further, so long as each hop is labelled.
- *A group has at most one container.* Multiple containers are conceivable;
  the rules of all of them would bind.

A system **declares** its position on each chosen rule (`/info`, see
`SPEC.md`). The benchmark then checks the system against **what it
declared**, and reports the declaration alongside the score. Conformance to
a declared policy is scored; the choice itself is not. A system that
declares "notes flow down, labelled" and does exactly that loses no points —
it loses points if its notes flow down *unlabelled*, or flow down when it
said they would not.
