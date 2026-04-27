from __future__ import annotations

from .experimental import build_mixer_block_control_frame, build_mixer_line_control_frame, build_mixer_tail_control_frame, build_mute_control_frame, build_source_control_frame, build_volume_control_frame
from .config import ProtocolConfig
from .protocol import apply_checksum, render_request
from .transports.base import Transport


class FA860Client:
    def __init__(self, transport: Transport, config: ProtocolConfig) -> None:
        self.transport = transport
        self.config = config

    async def __aenter__(self) -> "FA860Client":
        await self.transport.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.transport.disconnect()

    async def send_command(self, name: str, **params: object) -> bytes:
        if name not in self.config.commands:
            raise KeyError(f"unknown command: {name}")
        command = self.config.commands[name]
        payload = render_request(command.request, params)
        payload = apply_checksum(
            payload,
            checksum_name=self.config.protocol.checksum,
            enabled=command.append_checksum,
        )
        return await self.transport.transceive(
            payload,
            size=command.read_size,
            timeout=self.config.protocol.timeout,
        )

    async def send_raw(self, payload: bytes, read_size: int = 0) -> bytes:
        return await self.transport.transceive(
            payload,
            size=read_size,
            timeout=self.config.protocol.timeout,
        )

    async def send_frame(self, payload: bytes, read_size: int = 0) -> bytes:
        return await self.send_raw(payload, read_size=read_size)

    async def get_status(self) -> bytes:
        return await self.send_command("get_status")

    async def set_volume(self, volume: int) -> bytes:
        if not 0 <= volume <= 255:
            raise ValueError("volume must be between 0 and 255")
        return await self.send_command("set_volume", volume=volume)

    async def set_mute(self, mute: bool) -> bytes:
        return await self.send_command("set_mute", mute=1 if mute else 0)

    async def set_channel_mute(self, channel: int, mute: bool, read_size: int = 0) -> bytes:
        return await self.send_frame(build_mute_control_frame(channel, mute=mute), read_size=read_size)

    async def set_channel_sources(self, channel: int, *, line: bool, ble: bool, digital: bool, read_size: int = 0) -> bytes:
        mask = (0x02 if line else 0) | (0x04 if ble else 0) | (0x01 if digital else 0)
        return await self.send_frame(build_source_control_frame(mask, channel=channel), read_size=read_size)

    async def set_channel_volume(self, channel: int, db: int, mute: bool = False, read_size: int = 0) -> bytes:
        return await self.send_frame(build_volume_control_frame(channel, db=db, mute=mute), read_size=read_size)

    async def set_mixer_block(self, channel: int, block: int, values: tuple[int, ...], derived_seed: int | None = None, read_size: int = 0) -> bytes:
        return await self.send_frame(
            build_mixer_block_control_frame(channel=channel, block=block, values=values, derived_seed=derived_seed),
            read_size=read_size,
        )

    async def set_mixer_line_inputs(
        self,
        channel: int,
        values: tuple[int, ...],
        derived_seed: int | None = None,
        read_size: int = 0,
    ) -> bytes:
        return await self.send_frame(
            build_mixer_line_control_frame(channel=channel, values=values, derived_seed=derived_seed),
            read_size=read_size,
        )

    async def set_mixer_tail(
        self,
        channel: int,
        *,
        digital_l: int,
        digital_r: int,
        bt_l: int,
        bt_r: int,
        derived_seed: int | None = None,
        read_size: int = 0,
    ) -> bytes:
        return await self.send_frame(
            build_mixer_tail_control_frame(
                channel=channel,
                digital_l=digital_l,
                digital_r=digital_r,
                bt_l=bt_l,
                bt_r=bt_r,
                derived_seed=derived_seed,
            ),
            read_size=read_size,
        )

    async def recall_preset(self, preset: int) -> bytes:
        if not 0 <= preset <= 255:
            raise ValueError("preset must be between 0 and 255")
        return await self.send_command("recall_preset", preset=preset)
