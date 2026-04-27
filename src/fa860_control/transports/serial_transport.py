from __future__ import annotations

import asyncio

import serial
from serial.tools import list_ports

from .base import Transport


class SerialTransport(Transport):
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: serial.Serial | None = None

    async def connect(self) -> None:
        self._serial = await asyncio.to_thread(
            serial.Serial,
            self.port,
            self.baudrate,
            timeout=self.timeout,
        )

    async def disconnect(self) -> None:
        if self._serial is not None:
            await asyncio.to_thread(self._serial.close)
            self._serial = None

    async def send(self, payload: bytes) -> None:
        if self._serial is None:
            raise RuntimeError("serial transport is not connected")
        await asyncio.to_thread(self._serial.write, payload)

    async def receive(self, size: int = 0, timeout: float | None = None) -> bytes:
        if self._serial is None:
            raise RuntimeError("serial transport is not connected")
        if timeout is not None:
            self._serial.timeout = timeout
        expected = size or max(self._serial.in_waiting, 1)
        return await asyncio.to_thread(self._serial.read, expected)


def list_serial_ports() -> list[str]:
    return [port.device for port in list_ports.comports()]
