import asyncio
import time

from fa860_control.home_assistant import BridgeClientRuntime, execute_bridge_command, execute_bridge_http_command
from fa860_control.protocol import bytes_to_hex


class FakeClient:
    def __init__(self) -> None:
        self.config = type("Config", (), {"commands": {"get_status": object()}})()
        self.enter_count = 0
        self.exit_count = 0

    async def __aenter__(self) -> "FakeClient":
        self.enter_count += 1
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exit_count += 1
        return None

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


def test_execute_bridge_http_command_returns_bad_request_for_validation_errors() -> None:
    runtime = BridgeClientRuntime(lambda: FakeClient(), idle_disconnect_seconds=20)
    payload, status = execute_bridge_http_command(runtime, "mix_line", {"channel": 1, "values": [1, 2, 3]})
    runtime.close()

    assert status == 400
    assert payload == {"ok": False, "error": "values must contain exactly 8 items"}


def test_execute_bridge_http_command_returns_server_error_for_runtime_errors() -> None:
    class FailingClient(FakeClient):
        async def set_channel_volume(self, channel: int, db: int, mute: bool = False, read_size: int = 0) -> bytes:
            raise RuntimeError("device busy")

    runtime = BridgeClientRuntime(lambda: FailingClient(), idle_disconnect_seconds=20)
    payload, status = execute_bridge_http_command(runtime, "volume", {"channel": 4, "db": -20, "mute": False})
    runtime.close()

    assert status == 500
    assert payload == {"ok": False, "error": "device busy"}


def test_bridge_client_runtime_reuses_client_until_idle_disconnect() -> None:
    clients: list[FakeClient] = []

    def factory() -> FakeClient:
        client = FakeClient()
        clients.append(client)
        return client

    runtime = BridgeClientRuntime(factory, idle_disconnect_seconds=0.05)

    payload_1, status_1 = runtime.execute_http_command("mute", {"channel": 2, "mute": True})
    payload_2, status_2 = runtime.execute_http_command("volume", {"channel": 4, "db": -20, "mute": False})

    assert status_1 == 200
    assert payload_1["ok"] is True
    assert status_2 == 200
    assert payload_2["ok"] is True
    assert len(clients) == 1
    assert clients[0].enter_count == 1
    assert clients[0].exit_count == 0

    time.sleep(0.12)

    assert clients[0].exit_count == 1


def test_bridge_client_runtime_serializes_client_reuse_after_idle_disconnect() -> None:
    clients: list[FakeClient] = []

    def factory() -> FakeClient:
        client = FakeClient()
        clients.append(client)
        return client

    runtime = BridgeClientRuntime(factory, idle_disconnect_seconds=0.05)

    runtime.execute_http_command("mute", {"channel": 2, "mute": True})
    time.sleep(0.12)
    runtime.execute_http_command("mute", {"channel": 2, "mute": False})
    runtime.close()

    assert len(clients) == 2
    assert clients[0].enter_count == 1
    assert clients[0].exit_count == 1
    assert clients[1].enter_count == 1
    assert clients[1].exit_count == 1