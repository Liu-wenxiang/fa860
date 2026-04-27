from __future__ import annotations

import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import JSONDecodeError
import json
from typing import Any

from .client import FA860Client
from .config import ProtocolConfig, ProtocolOptions, load_protocol_config
from .protocol import bytes_to_hex
from .transports.ble_transport import BleTransport
from .transports.hid_transport import HidTransport
from .transports.mock import MockTransport
from .transports.serial_transport import SerialTransport
from .windows_setupapi import resolve_hid_path


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
            response = asyncio.run(self._run_command(name, params))
        except (JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)
            return
        self._send_json(response)

    async def _run_command(self, name: str, params: dict[str, object]) -> dict[str, object]:
        factory = type(self).client_factory
        async with factory() as client:
            raw = await execute_bridge_command(client, name, params)
        return {"ok": True, "command": name, "response_hex": bytes_to_hex(raw)}

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
    server = ThreadingHTTPServer((args.listen_host, args.listen_port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
