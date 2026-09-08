# Contributing

Two kinds of contribution, with different rules: **results** and **the
benchmark itself**.

## Publishing a result

A result says how a system scored. It is not a place to report the system's
defects — those belong on that system's own tracker, where its maintainers
can act on them.

A result pull request contains:

1. **The run file**, unedited, at `results/<system-id>/<timestamp>.json`.
   Produce it with `fmb run` and add it with `fmb submit`. It must validate
   (`fmb validate <file>`); CI checks this.
2. **The remarks already inside it** (`fmb run --note "..."`). This is where
   run-specific context belongs: a known open issue behind a failing family,
   a configuration that differs from the default. At most ten, and each is
   the team's own words, shown in the dashboard as theirs.
3. **One paragraph in the PR body** describing what was measured: the system
   version, and every component whose behaviour the result depends on. If
   part of the system is a model, name it. Two runs of one engine behind two
   different models are two systems, and a reader comparing results needs to
   know which one they are looking at.

Nothing else is required, and a bare run file with an honest paragraph is a
complete submission.

**Not in a result PR:** links to the system's bug tracker, a narrative of
what went wrong, or an argument about whether a measure is fair. If a
measure is wrong, that is an issue on this repository and it stands on its
own — it should not need a result to explain it.

A low score is a publishable result. `governance` is the *minimum* of the
governance families, so one weak guarantee sets the headline while the rest
of the run stays visible underneath; explaining which family carried the
number is useful, defending it is not.

## Adapters live with the system

This repository ships two adapters, and only two: `null` and `reference`.
They exist to prove the measures can be failed and passed, and they
implement `MODEL.md` and nothing else.

An adapter for a real system belongs with that system, maintained by the
people who can keep it correct as their system changes. The contract is in
`SPEC.md`: implement the seven endpoints over HTTP, or a Python class, and
point the runner at it.

    fmb run --system http://localhost:8000
    fmb run --system your_package.adapter:YourMemory

That boundary is what keeps a result honest. An adapter is a translation
layer, and the only thing it may do is translate: if it wraps content,
retries a decline, or reshapes a read to satisfy a measure, it is
manufacturing the result the measure exists to observe. Its authors are the
right people to hold that line, and its users are the right people to check
it — which is easier when it sits in the open next to the system it speaks
for, rather than in the tree of the benchmark grading it.

## Changing the benchmark

Issues and pull requests against the measures, the model, or the harness are
welcome, and the most valuable ones argue that a rule this model treats as
*forced* by the promise is really a *chosen* one, or the reverse.

Two things any change to the measures must keep true, both enforced by CI:

- the `null` baseline fails every governance family;
- the `reference` implementation passes all of them.

And one question to ask of any new measure, because three holes in the
suite have come from not asking it: **what would a system that holds
nothing score here?** A measure whose condition is an absence, a "no more
than one", or a "a note must never" is satisfied for free by a system that
declines what it is given. Assert the positive precondition first. See
`MEASURES.md`, "An absence is never a pass on its own".
