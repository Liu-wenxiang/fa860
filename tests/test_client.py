import asyncio
from argparse import Namespace

from fa860_control.client import FA860Client
from fa860_control.config import CommandSpec, ProtocolConfig, ProtocolOptions
from fa860_control.cli import _build_direct_operations, _is_direct_control_request
from fa860_control.protocol import bytes_to_hex
from fa860_control.transports.mock import MockTransport


def test_set_volume_uses_template() -> None:
    async def scenario() -> bytes:
        config = ProtocolConfig(
            protocol=ProtocolOptions(timeout=1.0, checksum="sum8"),
            commands={
                "set_volume": CommandSpec(
                    request="AA 55 02 01 {volume:02X}",
                    append_checksum=True,
                    read_size=4,
                )
            },
        )
        transport = MockTransport(lambda payload: payload)
        async with FA860Client(transport, config) as client:
            return await client.set_volume(16)

    response = asyncio.run(scenario())
    assert response == bytes.fromhex("AA55020110")[:4]


def test_set_mixer_tail_sends_verified_a1_22_frame() -> None:
    async def scenario() -> bytes:
        config = ProtocolConfig(
            protocol=ProtocolOptions(timeout=1.0, checksum="sum8"),
            commands={},
        )
        transport = MockTransport(lambda payload: payload)
        async with FA860Client(transport, config) as client:
            return await client.set_mixer_tail(channel=3, digital_l=11, digital_r=12, bt_l=9, bt_r=10, read_size=64)

    response = asyncio.run(scenario())
    assert bytes_to_hex(response[:24]) == "91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 0B 0C 09 0A EC AA"


def test_set_mixer_line_inputs_sends_verified_a1_21_frame() -> None:
    async def scenario() -> bytes:
        config = ProtocolConfig(
            protocol=ProtocolOptions(timeout=1.0, checksum="sum8"),
            commands={},
        )
        transport = MockTransport(lambda payload: payload)
        async with FA860Client(transport, config) as client:
            return await client.set_mixer_line_inputs(channel=3, values=(1, 2, 3, 4, 5, 6, 7, 8), read_size=64)

    response = asyncio.run(scenario())
    assert bytes_to_hex(response[:24]) == "91 91 91 EE A1 01 00 04 02 21 01 00 08 00 01 02 03 04 05 06 07 08 86 AA"


def test_direct_control_detects_mix_line_request() -> None:
    args = Namespace(
        channel=3,
        direct_mute=None,
        db=None,
        line=False,
        ble_source=False,
        digital=False,
        mix_line=[1, 2, 3, 4, 5, 6, 7, 8],
        mix_tail=None,
    )

    assert _is_direct_control_request(args) is True


def test_direct_control_builds_mix_line_operation() -> None:
    args = Namespace(
        channel=3,
        direct_mute=None,
        db=None,
        line=False,
        ble_source=False,
        digital=False,
        mix_line=[1, 2, 3, 4, 5, 6, 7, 8],
        mix_tail=None,
    )

    operations = _build_direct_operations(args)
    assert operations == [
        ("mix-line", bytes.fromhex("91 91 91 EE A1 01 00 04 02 21 01 00 08 00 01 02 03 04 05 06 07 08 86 AA") + bytes(40)),
    ]


def test_direct_control_builds_mix_tail_operation() -> None:
    args = Namespace(
        channel=3,
        direct_mute=None,
        db=None,
        line=False,
        ble_source=False,
        digital=False,
        mix_line=None,
        mix_tail=[11, 12, 9, 10],
    )

    operations = _build_direct_operations(args)
    assert operations == [
        ("mix-tail", bytes.fromhex("91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 0B 0C 09 0A EC AA") + bytes(40)),
    ]
