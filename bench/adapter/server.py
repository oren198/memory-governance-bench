"""Serve any Python adapter over the canonical HTTP binding.

Used to prove the two bindings are the same contract: the same system, driven
in-process and over HTTP, must produce byte-identical scenario outcomes. Also
a worked reference for anyone implementing the endpoints in another language.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bench.adapter.protocol import Agent, MemorySystem, Unsupported, World, Write


def _shown_json(item) -> dict:
    out = {
        "content": item.content,
        "kind": item.kind,
        "origin": item.origin,
        "binding": item.binding,
    }
    for field in ("via", "attributed_to", "receipt", "event"):
        value = getattr(item, field)
        if value is not None:
            out[field] = value
    return out


def make_handler(system: MemorySystem):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args) -> None:  # silence the default stderr log
            return

        def _send(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            length = int(self.headers.get("content-length") or 0)
            return json.loads(self.rfile.read(length) or b"{}")

        @staticmethod
        def _agent(d: dict) -> Agent:
            a = d["agent"]
            return Agent(id=a["id"], group=a["group"], owner=bool(a.get("owner", False)))

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/info":
                self._send(404, {"error": "not found"})
                return
            info = system.info()
            self._send(200, {
                "id": info.id, "name": info.name, "version": info.version,
                "declarations": {
                    "notes_flow_down": info.declarations.notes_flow_down,
                    "listening_is_transitive": info.declarations.listening_is_transitive,
                    "multiple_containers": info.declarations.multiple_containers,
                },
            })

        def do_POST(self) -> None:  # noqa: N802
            try:
                body = self._body()
                if self.path == "/world":
                    system.world(World(
                        groups=tuple(body.get("groups", ())),
                        part_of=tuple(tuple(p) for p in body.get("part_of", ())),
                        listens_to=tuple(tuple(p) for p in body.get("listens_to", ())),
                        owner_groups=tuple(body.get("owner_groups", ())),
                        bound=int(body.get("bound", 500)),
                    ))
                    self._send(200, {})
                elif self.path == "/write":
                    r = system.write(self._agent(body), Write(
                        content=body["content"], kind=body["kind"],
                        replaces=body.get("replaces"), subject=body.get("subject"),
                    ))
                    self._send(200, {"id": r.id, "accepted": r.accepted, "reason": r.reason})
                elif self.path in ("/announce", "/retract"):
                    op = system.announce if self.path == "/announce" else system.retract
                    r = op(self._agent(body), body["receipt_id"])
                    self._send(200, {"id": r.id, "accepted": r.accepted, "reason": r.reason})
                elif self.path == "/read":
                    read = system.read(self._agent(body))
                    payload = {
                        "items": [_shown_json(i) for i in read.items],
                        "words": read.words,
                    }
                    if read.dropped is not None:
                        payload["dropped"] = read.dropped
                    self._send(200, payload)
                elif self.path == "/settle":
                    system.settle()
                    self._send(200, {})
                else:
                    self._send(404, {"error": "not found"})
            except Unsupported as exc:
                self._send(501, {"unsupported": str(exc)})
            except Exception as exc:  # surface as a server error, not a hang
                self._send(500, {"error": repr(exc)})

    return Handler


class ServedSystem:
    """Run a Python adapter on a background HTTP server. Use as a context
    manager; `url` is the base to hand an :class:`HttpSystem`."""

    def __init__(self, system: MemorySystem, host: str = "127.0.0.1", port: int = 0) -> None:
        self._httpd = ThreadingHTTPServer((host, port), make_handler(system))
        self.url = f"http://{host}:{self._httpd.server_address[1]}"

    def __enter__(self) -> "ServedSystem":
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
