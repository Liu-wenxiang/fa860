from __future__ import annotations

from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send(self, payload: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    async def receive(self, size: int = 0, timeout: float | None = None) -> bytes:
        raise NotImplementedError

    async def transceive(self, payload: bytes, size: int = 0, timeout: float | None = None) -> bytes:
        await self.send(payload)
        if size <= 0:
            return b""
        return await self.receive(size=size, timeout=timeout)
