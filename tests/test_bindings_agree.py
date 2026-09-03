"""HTTP is the canonical binding; the Python one must be the same contract.

The same system, driven in-process and over HTTP, must produce identical
scenario outcomes. This is the only thing that keeps the two bindings from
drifting apart, and it gives us an HTTP test target with no real system.
"""

from bench.adapter.http import HttpSystem
from bench.adapter.null import NullMemory
from bench.adapter.server import ServedSystem
from bench.runner import run


def _outcomes(result):
    return {s["id"]: s["passed"] for s in result.scenarios}


def test_http_and_in_process_agree():
    direct = run(NullMemory())
    with ServedSystem(NullMemory()) as served:
        over_http = run(HttpSystem(served.url))
    assert _outcomes(direct) == _outcomes(over_http)
    assert direct.headline == over_http.headline


def test_http_reports_call_count():
    with ServedSystem(NullMemory()) as served:
        system = HttpSystem(served.url)
        result = run(system, families=["C"])
    assert result.cost["calls"] and result.cost["calls"] > 0


def test_unsupported_surfaces_as_501():
    from bench.adapter.protocol import Agent, Unsupported

    class NoRetract(NullMemory):
        def retract(self, agent, receipt_id):
            raise Unsupported("retract")

    with ServedSystem(NoRetract()) as served:
        system = HttpSystem(served.url)
        try:
            system.retract(Agent(id="a", group="g"), "x")
        except Unsupported as exc:
            assert "retract" in str(exc)
        else:
            raise AssertionError("expected Unsupported")


def test_unsupported_is_reported_not_passed():
    from bench.adapter.protocol import Unsupported

    class NoRetract(NullMemory):
        def retract(self, agent, receipt_id):
            raise Unsupported("retract")

    result = run(NoRetract(), families=["F"])
    unsupported = [s for s in result.scenarios if s["unsupported"]]
    assert unsupported, "an unsupported operation must be recorded, never silently passed"
    assert all(not s["passed"] for s in unsupported)
    assert result.families["F"]["unsupported"] == len(unsupported)
