"""HTTP client adapter — the canonical binding (SPEC.md §2.1).

Drives any system that serves the seven endpoints, in any language. A `501`
with `{"unsupported": ...}` raises :class:`Unsupported`, which the harness
reports distinctly rather than scoring as a pass.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from bench.adapter.protocol import (
    Agent,
    Declarations,
    Info,
    Read,
    Receipt,
    Shown,
    Unsupported,
    World,
    Write,
)


class HttpSystem:
    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.name = self.base
        self.calls = 0

    # --- transport --------------------------------------------------------

    def _call(self, path: str, body: dict | None = None, method: str = "POST") -> dict:
        url = f"{self.base}{path}"
        data = json.dumps(body or {}).encode() if method == "POST" else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"content-type": "application/json"},
        )
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode() or "{}"
        except urllib.error.HTTPError as exc:
            if exc.code == 501:
                payload = {}
                try:
                    payload = json.loads(exc.read().decode() or "{}")
                except Exception:
                    pass
                raise Unsupported(payload.get("unsupported", path)) from None
            raise
        return json.loads(raw)

    @staticmethod
    def _agent(agent: Agent) -> dict:
        return {"id": agent.id, "group": agent.group, "owner": agent.owner}

    # --- the seven operations --------------------------------------------

    def info(self) -> Info:
        d = self._call("/info", method="GET")
        decl = d.get("declarations") or {}
        return Info(
            id=d.get("id", "unknown"),
            name=d.get("name", d.get("id", "unknown")),
            version=d.get("version", "0"),
            declarations=Declarations(
                notes_flow_down=bool(decl.get("notes_flow_down", False)),
                listening_is_transitive=bool(decl.get("listening_is_transitive", False)),
                multiple_containers=bool(decl.get("multiple_containers", False)),
            ),
        )

    def world(self, world: World) -> None:
        self._call("/world", {
            "groups": list(world.groups),
            "part_of": [list(p) for p in world.part_of],
            "listens_to": [list(p) for p in world.listens_to],
            "owner_groups": list(world.owner_groups),
            "bound": world.bound,
        })

    def write(self, agent: Agent, write: Write) -> Receipt:
        d = self._call("/write", {
            "agent": self._agent(agent),
            "content": write.content,
            "kind": write.kind,
            "replaces": write.replaces,
            "subject": write.subject,
        })
        return Receipt(id=d.get("id", ""), accepted=bool(d.get("accepted", False)),
                       reason=d.get("reason"))

    def announce(self, agent: Agent, receipt_id: str) -> Receipt:
        d = self._call("/announce", {"agent": self._agent(agent), "receipt_id": receipt_id})
        return Receipt(id=d.get("id", receipt_id), accepted=bool(d.get("accepted", False)),
                       reason=d.get("reason"))

    def retract(self, agent: Agent, receipt_id: str) -> Receipt:
        d = self._call("/retract", {"agent": self._agent(agent), "receipt_id": receipt_id})
        return Receipt(id=d.get("id", receipt_id), accepted=bool(d.get("accepted", False)),
                       reason=d.get("reason"))

    def read(self, agent: Agent) -> Read:
        d = self._call("/read", {"agent": self._agent(agent)})
        items = tuple(
            Shown(
                content=i.get("content", ""),
                kind=i.get("kind", "note"),
                origin=i.get("origin", ""),
                binding=bool(i.get("binding", False)),
                via=i.get("via"),
                attributed_to=i.get("attributed_to"),
                receipt=i.get("receipt"),
                event=i.get("event"),
            )
            for i in d.get("items", [])
        )
        return Read(items=items, words=int(d.get("words", 0)), dropped=d.get("dropped"))

    def settle(self) -> None:
        self._call("/settle", {})
