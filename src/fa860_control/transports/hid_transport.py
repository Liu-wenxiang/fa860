from __future__ import annotations

import asyncio

try:
    import hid
except ImportError:  # pragma: no cover
    hid = None

from .base import Transport


class HidTransport(Transport):
    def __init__(
        self,
        *,
        path: str | None = None,
        vendor_id: int | None = None,
        product_id: int | None = None,
        serial_number: str | None = None,
        read_size: int = 64,
        prepend_zero_report_id: bool = True,
    ) -> None:
        if hid is None:
            raise RuntimeError("hidapi is not installed")
        self.path = path
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.serial_number = serial_number
        self.read_size = read_size
        self.prepend_zero_report_id = prepend_zero_report_id
        self._device: hid.device | None = None

    async def connect(self) -> None:
        device = hid.device()
        if self.path:
            await asyncio.to_thread(device.open_path, self.path.encode("utf-8"))
        else:
            if self.vendor_id is None or self.product_id is None:
                raise ValueError("hid transport requires --hid-path or both --vendor-id and --product-id")
            await asyncio.to_thread(device.open, self.vendor_id, self.product_id, self.serial_number or None)
        self._device = device

    async def disconnect(self) -> None:
        if self._device is not None:
            await asyncio.to_thread(self._device.close)
            self._device = None

    async def send(self, payload: bytes) -> None:
        if self._device is None:
            raise RuntimeError("hid transport is not connected")
        data = (b"\x00" + payload) if self.prepend_zero_report_id else payload
        written = await asyncio.to_thread(self._device.write, data)
        if written <= 0:
            raise RuntimeError("hid write failed")

    async def receive(self, size: int = 0, timeout: float | None = None) -> bytes:
        if self._device is None:
            raise RuntimeError("hid transport is not connected")
        read_size = size or self.read_size
        if timeout is not None:
            await asyncio.to_thread(self._device.set_nonblocking, 0)
        data = await asyncio.to_thread(self._device.read, read_size)
        return bytes(data)


def list_hid_devices() -> list[dict[str, object]]:
    if hid is None:
        raise RuntimeError("hidapi is not installed")
    devices = []
    for item in hid.enumerate():
        path = item.get("path")
        if isinstance(path, bytes):
            path = path.decode("utf-8", errors="ignore")
        devices.append(
            {
                "path": path,
                "vendor_id": item.get("vendor_id"),
                "product_id": item.get("product_id"),
                "manufacturer_string": item.get("manufacturer_string"),
                "product_string": item.get("product_string"),
                "serial_number": item.get("serial_number"),
                "usage_page": item.get("usage_page"),
                "usage": item.get("usage"),
            }
        )
    return devices
