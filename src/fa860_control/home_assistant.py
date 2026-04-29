from __future__ import annotations

import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import JSONDecodeError
import json
import logging
import threading
from typing import Any

from .client import FA860Client
from .config import ProtocolConfig, ProtocolOptions, load_protocol_config
from .protocol import bytes_to_hex
from .transports.ble_transport import BleTransport
from .transports.hid_transport import HidTransport
from .transports.mock import MockTransport
from .transports.serial_transport import SerialTransport
from .windows_setupapi import resolve_hid_path


_LOGGER = logging.getLogger(__name__)
DEFAULT_IDLE_DISCONNECT_SECONDS = 20.0


SUPPORTED_DIRECT_COMMANDS = (
    "mute",
    "set_channel_mute",
    "source",
    "set_channel_sources",
    "volume",
    "set_channel_volume",
    "mix_line",
    "set_mixer_line_inputs",
    "mix_tail",
    "set_mixer_tail",
)


def _coerce_values(values: object, expected_length: int) -> tuple[int, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"values must be a list with exactly {expected_length} items")
    converted = tuple(int(value) for value in values)
    if len(converted) != expected_length:
        raise ValueError(f"values must contain exactly {expected_length} items")
    return converted


async def execute_bridge_command(client: FA860Client, name: str, params: dict[str, object]) -> bytes:
    read_size = int(params.get("read_size", 0))
    if name in ("mute", "set_channel_mute"):
        return await client.set_channel_mute(
            channel=int(params["channel"]),
            mute=bool(params["mute"]),
            read_size=read_size,
        )
    if name in ("source", "set_channel_sources"):
        return await client.set_channel_sources(
            channel=int(params["channel"]),
            line=bool(params.get("line", False)),
            ble=bool(params.get("ble", False)),
            digital=bool(params.get("digital", False)),
            read_size=read_size,
        )
    if name in ("volume", "set_channel_volume"):
        return await client.set_channel_volume(
            channel=int(params["channel"]),
            db=int(params["db"]),
            mute=bool(params.get("mute", False)),
            read_size=read_size,
        )
    if name in ("mix_line", "set_mixer_line_inputs"):
        return await client.set_mixer_line_inputs(
            channel=int(params["channel"]),
            values=_coerce_values(params["values"], 8),
            read_size=read_size,
        )
    if name in ("mix_tail", "set_mixer_tail"):
        return await client.set_mixer_tail(
            channel=int(params["channel"]),
            digital_l=int(params["digital_l"]),
            digital_r=int(params["digital_r"]),
            bt_l=int(params["bt_l"]),
            bt_r=int(params["bt_r"]),
            read_size=read_size,
        )
    if name not in client.config.commands:
        raise ValueError("bridge template commands require --config with matching command definitions")
    return await client.send_command(name, **params)


async def _run_bridge_command(client_factory: Any, name: str, params: dict[str, object]) -> dict[str, object]:
    async with client_factory() as client:
        raw = await execute_bridge_command(client, name, params)
    return {"ok": True, "command": name, "response_hex": bytes_to_hex(raw)}


class BridgeClientRuntime:
    def __init__(self, client_factory: Any, idle_disconnect_seconds: float = DEFAULT_IDLE_DISCONNECT_SECONDS) -> None:
        self._client_factory = client_factory
        self._idle_disconnect_seconds = idle_disconnect_seconds
        self._lock = threading.Lock()
        self._client: FA860Client | None = None
        self._idle_timer: threading.Timer | None = None

    def execute_http_command(self, name: str, params: dict[str, object]) -> tuple[dict[str, object], int]:
        with self._lock:
            self._cancel_idle_timer_locked()
            try:
                client = self._ensure_client_locked()
                raw = asyncio.run(execute_bridge_command(client, name, params))
            except (KeyError, TypeError, ValueError) as exc:
                self._schedule_idle_disconnect_locked()
                return {"ok": False, "error": str(exc)}, 400
            except Exception as exc:
                _LOGGER.exception("FA860 bridge command failed: %s", name)
                self._schedule_idle_disconnect_locked()
                return {"ok": False, "error": str(exc) or exc.__class__.__name__}, 500
            self._schedule_idle_disconnect_locked()
            return {"ok": True, "command": name, "response_hex": bytes_to_hex(raw)}, 200

    def close(self) -> None:
        with self._lock:
            self._cancel_idle_timer_locked()
            self._disconnect_client_locked()

    def _ensure_client_locked(self) -> FA860Client:
        if self._client is None:
            client = self._client_factory()
            asyncio.run(client.__aenter__())
            self._client = client
        return self._client

    def _schedule_idle_disconnect_locked(self) -> None:
        if self._idle_disconnect_seconds <= 0:
            return
        self._idle_timer = threading.Timer(self._idle_disconnect_seconds, self._disconnect_due_to_idle)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _cancel_idle_timer_locked(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _disconnect_due_to_idle(self) -> None:
        with self._lock:
            self._idle_timer = None
            self._disconnect_client_locked()

    def _disconnect_client_locked(self) -> None:
        if self._client is None:
            return
        client = self._client
        self._client = None
        asyncio.run(client.__aexit__(None, None, None))


def execute_bridge_http_command(runtime: BridgeClientRuntime, name: str, params: dict[str, object]) -> tuple[dict[str, object], int]:
    return runtime.execute_http_command(name, params)


def build_transport(args: argparse.Namespace):
    if args.transport == "serial":
        return SerialTransport(port=args.port, baudrate=args.baudrate, timeout=args.timeout)
    if args.transport == "ble":
        return BleTransport(
            address=args.address,
            write_uuid=args.write_uuid,
            notify_uuid=args.notify_uuid,
            timeout=args.timeout,
        )
    if args.transport == "hid":
        hid_path = resolve_hid_path(args.hid_path, vid=args.vendor_id, pid=args.product_id)
        return HidTransport(
            path=hid_path,
            vendor_id=args.vendor_id,
            product_id=args.product_id,
            serial_number=args.serial_number,
            read_size=args.hid_read_size,
            prepend_zero_report_id=args.hid_prepend_zero_report_id,
        )
    if args.transport == "mock":
        return MockTransport()
    raise ValueError(f"unsupported transport: {args.transport}")


class RequestHandler(BaseHTTPRequestHandler):
    client_factory: Any = None
    bridge_runtime: BridgeClientRuntime | None = None

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"ok": True})
            return
        if self.path == "/capabilities":
            self._send_json({
                "ok": True,
                "direct_commands": list(SUPPORTED_DIRECT_COMMANDS),
            })
            return
        if self.path != "/health":
            self.send_error(404)
            return

    def do_POST(self) -> None:
        if self.path != "/command":
            self.send_error(404)
            return
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            payload = json.loads(body.decode("utf-8"))
            name = payload["name"]
            params = payload.get("params", {})
        except (JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)
            return
        runtime = type(self).bridge_runtime
        if runtime is None:
            self._send_json({"ok": False, "error": "bridge runtime is not configured"}, status=500)
            return
        response, status = execute_bridge_http_command(runtime, name, params)
        self._send_json(response, status=status)

    def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expose FA860 commands over HTTP for Home Assistant")
    parser.add_argument("--config")
    parser.add_argument("--transport", choices=["serial", "ble", "hid", "mock"], required=True)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=9123)
    parser.add_argument("--port")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--address")
    parser.add_argument("--write-uuid")
    parser.add_argument("--notify-uuid")
    parser.add_argument("--hid-path")
    parser.add_argument("--vendor-id", type=lambda value: int(value, 0))
    parser.add_argument("--product-id", type=lambda value: int(value, 0))
    parser.add_argument("--serial-number")
    parser.add_argument("--hid-read-size", type=int, default=64)
    parser.add_argument("--hid-prepend-zero-report-id", dest="hid_prepend_zero_report_id", action="store_true")
    parser.add_argument("--no-hid-prepend-zero-report-id", dest="hid_prepend_zero_report_id", action="store_false")
    parser.set_defaults(hid_prepend_zero_report_id=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.config:
        config = load_protocol_config(args.config)
    else:
        config = ProtocolConfig(protocol=ProtocolOptions(timeout=args.timeout), commands={})

    def client_factory() -> FA860Client:
        return FA860Client(build_transport(args), config)

    RequestHandler.client_factory = staticmethod(client_factory)
    bridge_runtime = BridgeClientRuntime(client_factory)
    RequestHandler.bridge_runtime = bridge_runtime
    server = ThreadingHTTPServer((args.listen_host, args.listen_port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bridge_runtime.close()
        server.server_close()


if __name__ == "__main__":
    main()
