"""Strata adapter — NOT YET RUN AGAINST A LIVE ENGINE.

Read `adapters/strata/README.md` before touching this file. In particular:
build the fleet in-process with explicit paths. Driving Strata through its
CLI or a running server once reached an operator's real store and destroyed
real memory.

This is a skeleton: the mapping is written down, and every operation the
engine has no equivalent of raises `Unsupported` so the benchmark reports it
honestly rather than scoring a silent pass. Filling it in requires the Strata
library, which this repository does not depend on.
"""

from __future__ import annotations

from bench.adapter.protocol import (
    Agent,
    Declarations,
    Info,
    Read,
    Receipt,
    Unsupported,
    World,
    Write,
)

# groups          -> scopes
# part_of         -> chain edges (adjacent strata only; depth maps to ordinal)
# listens_to      -> reference edges
# owner_groups    -> scopes the operator attaches memory to
# origin / via    -> origin_scope_id / relay_scope_id
#
# Expected failures, with reasons, per the README:
#   S4b, S5, S7, F0  — no withdrawal event exists in a read
#   S7               — nothing reaches a scope that absorbed a claim
#   P3               — one chain parent only (declared, so P3 is not issued)


class StrataMemory:
    name = "strata"

    def __init__(self, workdir: str | None = None) -> None:
        self.workdir = workdir
        raise NotImplementedError(
            "the Strata adapter is a skeleton: see adapters/strata/README.md. "
            "Build it in-process (FleetConfig.load on a temp fleet.yaml, explicit "
            "db and summaries paths); never through the CLI or a running server."
        )

    def info(self) -> Info:
        return Info(
            id="strata",
            name="Strata",
            version="unknown",
            declarations=Declarations(
                notes_flow_down=False,          # ADR 0013 D1
                listening_is_transitive=False,  # ADR 0013 D3
                multiple_containers=False,      # one chain parent per scope
            ),
        )

    def world(self, world: World) -> None:
        raise NotImplementedError

    def write(self, agent: Agent, write: Write) -> Receipt:
        raise NotImplementedError

    def announce(self, agent: Agent, receipt_id: str) -> Receipt:
        raise NotImplementedError

    def retract(self, agent: Agent, receipt_id: str) -> Receipt:
        # Retirement exists for binding items only; a note is dropped when
        # memory is next curated, not un-said by act.
        raise Unsupported("retract")

    def read(self, agent: Agent) -> Read:
        raise NotImplementedError

    def settle(self) -> None:
        raise NotImplementedError
