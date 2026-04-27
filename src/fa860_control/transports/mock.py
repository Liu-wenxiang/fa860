from __future__ import annotations

from collections.abc import Callable

from .base import Transport


class MockTransport(Transport):
    def __init__(self, responder: Callable[[bytes], bytes] | None = None) -> None:
        self._responder = responder or (lambda payload: b"ACK" + payload[:1])
        self.connected = False
        self.last_payload = b""
        self._last_response = b""

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def send(self, payload: bytes) -> None:
        self.last_payload = payload
        self._last_response = self._responder(payload)

    async def receive(self, size: int = 0, timeout: float | None = None) -> bytes:
        if size > 0:
            return self._last_response[:size]
        return self._last_response
