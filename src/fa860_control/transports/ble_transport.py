from __future__ import annotations

from dataclasses import dataclass

try:
    from bleak import BleakClient, BleakScanner
except ImportError:  # pragma: no cover
    BleakClient = None
    BleakScanner = None

from .base import Transport


@dataclass(slots=True)
class BleDevice:
    name: str | None
    address: str


class BleTransport(Transport):
    def __init__(self, address: str, write_uuid: str, notify_uuid: str | None = None, timeout: float = 1.0) -> None:
        if BleakClient is None:
            raise RuntimeError("bleak is not installed; use pip install -e .[ble]")
        self.address = address
        self.write_uuid = write_uuid
        self.notify_uuid = notify_uuid
        self.timeout = timeout
        self._client = BleakClient(address, timeout=timeout)
        self._last_notification = b""

    async def connect(self) -> None:
        await self._client.connect()
        if self.notify_uuid:
            await self._client.start_notify(self.notify_uuid, self._on_notification)

    async def disconnect(self) -> None:
        if self.notify_uuid and self._client.is_connected:
            await self._client.stop_notify(self.notify_uuid)
        await self._client.disconnect()

    async def send(self, payload: bytes) -> None:
        await self._client.write_gatt_char(self.write_uuid, payload)

    async def receive(self, size: int = 0, timeout: float | None = None) -> bytes:
        return self._last_notification[:size] if size > 0 else self._last_notification

    def _on_notification(self, _: str, data: bytearray) -> None:
        self._last_notification = bytes(data)


async def scan_ble() -> list[BleDevice]:
    if BleakScanner is None:
        raise RuntimeError("bleak is not installed; use pip install -e .[ble]")
    devices = await BleakScanner.discover()
    return [BleDevice(name=device.name, address=device.address) for device in devices]
