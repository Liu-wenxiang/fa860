import asyncio

from fa860_control.home_assistant import execute_bridge_command
from fa860_control.protocol import bytes_to_hex


class FakeClient:
    def __init__(self) -> None:
        self.config = type("Config", (), {"commands": {"get_status": object()}})()

    async def set_channel_mute(self, channel: int, mute: bool, read_size: int = 0) -> bytes:
        return f"mute:{channel}:{int(mute)}:{read_size}".encode("ascii")

    async def set_channel_sources(self, channel: int, *, line: bool, ble: bool, digital: bool, read_size: int = 0) -> bytes:
        return f"source:{channel}:{int(line)}:{int(ble)}:{int(digital)}:{read_size}".encode("ascii")

    async def set_channel_volume(self, channel: int, db: int, mute: bool = False, read_size: int = 0) -> bytes:
        return f"volume:{channel}:{db}:{int(mute)}:{read_size}".encode("ascii")

    async def set_mixer_line_inputs(self, channel: int, values: tuple[int, ...], derived_seed: int | None = None, read_size: int = 0) -> bytes:
        return f"mix_line:{channel}:{','.join(str(v) for v in values)}:{read_size}".encode("ascii")

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
        return f"mix_tail:{channel}:{digital_l}:{digital_r}:{bt_l}:{bt_r}:{read_size}".encode("ascii")

    async def send_command(self, name: str, **params: object) -> bytes:
        return f"command:{name}:{sorted(params.items())}".encode("ascii")


def test_execute_bridge_command_dispatches_direct_mute() -> None:
    response = asyncio.run(execute_bridge_command(FakeClient(), "mute", {"channel": 2, "mute": True}))
    assert response == b"mute:2:1:0"


def test_execute_bridge_command_dispatches_direct_source() -> None:
    response = asyncio.run(
        execute_bridge_command(
            FakeClient(),
            "source",
            {"channel": 3, "line": True, "ble": False, "digital": True, "read_size": 64},
        )
    )
    assert response == b"source:3:1:0:1:64"


def test_execute_bridge_command_dispatches_direct_volume() -> None:
    response = asyncio.run(execute_bridge_command(FakeClient(), "volume", {"channel": 4, "db": -20, "mute": False}))
    assert response == b"volume:4:-20:0:0"


def test_execute_bridge_command_dispatches_mix_line() -> None:
    response = asyncio.run(
        execute_bridge_command(
            FakeClient(),
            "mix_line",
            {"channel": 1, "values": [1, 2, 3, 4, 5, 6, 7, 8]},
        )
    )
    assert response == b"mix_line:1:1,2,3,4,5,6,7,8:0"


def test_execute_bridge_command_dispatches_mix_tail() -> None:
    response = asyncio.run(
        execute_bridge_command(
            FakeClient(),
            "mix_tail",
            {"channel": 5, "digital_l": 11, "digital_r": 12, "bt_l": 9, "bt_r": 10, "read_size": 64},
        )
    )
    assert response == b"mix_tail:5:11:12:9:10:64"


def test_execute_bridge_command_falls_back_to_template_command() -> None:
    response = asyncio.run(execute_bridge_command(FakeClient(), "get_status", {"zone": 1}))
    assert bytes_to_hex(response) == bytes_to_hex(b"command:get_status:[('zone', 1)]")


def test_execute_bridge_command_validates_mix_line_length() -> None:
    try:
        asyncio.run(execute_bridge_command(FakeClient(), "mix_line", {"channel": 1, "values": [1, 2, 3]}))
    except ValueError as exc:
        assert str(exc) == "values must contain exactly 8 items"
    else:
        raise AssertionError("expected mix_line values validation error")


def test_execute_bridge_command_requires_config_for_template_commands() -> None:
    class NoTemplateClient(FakeClient):
        def __init__(self) -> None:
            self.config = type("Config", (), {"commands": {}})()

    try:
        asyncio.run(execute_bridge_command(NoTemplateClient(), "get_status", {}))
    except ValueError as exc:
        assert str(exc) == "bridge template commands require --config with matching command definitions"
    else:
        raise AssertionError("expected template command config error")