from __future__ import annotations

import argparse
import asyncio
import json

from .client import FA860Client
from .config import load_protocol_config
from .experimental import (
    MIXER_AUX_OPCODE,
    MIXER_LINE_OPCODE,
    build_a1_mixer_aux_frame,
    build_a1_mixer_block_frame,
    build_a1_mixer_frame,
    build_mute_frame,
    build_mixer_block_control_frame,
    build_mixer_line_control_frame,
    build_mixer_tail_control_frame,
    build_source_frame,
    build_source_mask,
    build_a1_volume_frame,
    build_mute_control_frame,
    mixer_block_labels,
    mixer_section_labels,
    parse_a1_mixer_block_frame,
    build_source_control_frame,
    build_volume_control_frame,
    observed_mute_target,
)
from .protocol import bytes_to_hex, hex_to_bytes
from .transports.ble_transport import BleTransport, scan_ble
from .transports.hid_transport import HidTransport, list_hid_devices
from .transports.mock import MockTransport
from .transports.serial_transport import SerialTransport, list_serial_ports
from .windows_setupapi import enumerate_hid_interfaces, resolve_hid_path


def parse_key_value(items: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in items:
        key, value = item.split("=", 1)
        result[key] = int(value) if value.isdigit() else value
    return result


def add_transport_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--transport", choices=["serial", "ble", "hid", "mock"], required=True)
    parser.add_argument("--timeout", type=float, default=1.0)
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


def build_transport(args: argparse.Namespace):
    if args.transport == "serial":
        if not args.port:
            raise ValueError("serial transport requires --port")
        return SerialTransport(args.port, baudrate=args.baudrate, timeout=args.timeout)
    if args.transport == "ble":
        if not args.address or not args.write_uuid:
            raise ValueError("ble transport requires --address and --write-uuid")
        return BleTransport(args.address, args.write_uuid, notify_uuid=args.notify_uuid, timeout=args.timeout)
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
    return MockTransport()


async def run_send(args: argparse.Namespace) -> None:
    config = load_protocol_config(args.config)
    transport = build_transport(args)
    params = parse_key_value(args.param or [])
    async with FA860Client(transport, config) as client:
        response = await client.send_command(args.command, **params)
    print(bytes_to_hex(response))


async def run_raw(args: argparse.Namespace) -> None:
    config = load_protocol_config(args.config)
    transport = build_transport(args)
    payload = hex_to_bytes(args.hex)
    async with FA860Client(transport, config) as client:
        response = await client.send_raw(payload, read_size=args.read_size)
    print(bytes_to_hex(response))


async def run_experimental_frame(args: argparse.Namespace, payload: bytes) -> None:
    print(bytes_to_hex(payload))
    if args.transport == "mock" and not args.send:
        return
    if not args.send:
        return
    transport = build_transport(args)
    config = load_protocol_config(args.config)
    async with FA860Client(transport, config) as client:
        response = await client.send_raw(payload, read_size=args.read_size)
    if response:
        print(bytes_to_hex(response))


def main() -> None:
    parser = argparse.ArgumentParser(description="FA860 control CLI")

    parser.add_argument("--config", default="examples/fa860.example.json")
    parser.add_argument("--transport", choices=["serial", "ble", "hid", "mock"], default="hid")
    parser.add_argument("--timeout", type=float, default=1.0)
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
    parser.add_argument("--channel", "--ch", dest="channel", type=int)
    parser.add_argument("--mute", dest="direct_mute", action="store_true")
    parser.add_argument("--unmute", dest="direct_mute", action="store_false")
    parser.set_defaults(direct_mute=None)
    parser.add_argument("--line", "--l", dest="line", action="store_true")
    parser.add_argument("--ble-source", "--b", dest="ble_source", action="store_true")
    parser.add_argument("--digital", "--d", dest="digital", action="store_true")
    parser.add_argument("--db", type=int)
    parser.add_argument("--mix-line", "--ml", dest="mix_line", type=int, nargs=8, metavar=("LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8"))
    parser.add_argument("--mix-tail", "--mt", dest="mix_tail", type=int, nargs=4, metavar=("DIGITAL_L", "DIGITAL_R", "BT_L", "BT_R"))
    parser.add_argument("--read-size", type=int, default=0)

    subparsers = parser.add_subparsers(dest="subcommand")

    ports_parser = subparsers.add_parser("ports", help="List available serial ports")
    ports_parser.set_defaults(handler=lambda _: print("\n".join(list_serial_ports())))

    ble_parser = subparsers.add_parser("scan-ble", help="Scan BLE devices")
    ble_parser.set_defaults(handler=lambda _: asyncio.run(_scan_ble_command()))

    hid_parser = subparsers.add_parser("hid-devices", help="List HID devices")
    hid_parser.set_defaults(handler=lambda _: _list_hid_devices())

    setupapi_parser = subparsers.add_parser("setupapi-hid", help="List HID interface paths via Windows SetupAPI")
    setupapi_parser.add_argument("--vendor-id", type=lambda value: int(value, 0))
    setupapi_parser.add_argument("--product-id", type=lambda value: int(value, 0))
    setupapi_parser.set_defaults(handler=lambda args: _list_setupapi_hid(args))

    send_parser = subparsers.add_parser("send", help="Send a named command")
    send_parser.add_argument("--config", required=True)
    send_parser.add_argument("--command", required=True)
    send_parser.add_argument("--param", action="append")
    add_transport_args(send_parser)
    send_parser.set_defaults(handler=lambda args: asyncio.run(run_send(args)))

    raw_parser = subparsers.add_parser("raw", help="Send raw hex payload")
    raw_parser.add_argument("--config", required=True)
    raw_parser.add_argument("--hex", required=True)
    raw_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(raw_parser)
    raw_parser.set_defaults(handler=lambda args: asyncio.run(run_raw(args)))

    source_control_parser = subparsers.add_parser("source", help="Set per-channel source enable state")
    source_control_parser.add_argument("--config", default="examples/fa860.example.json")
    source_control_parser.add_argument("--channel", "--ch", dest="channel", type=int, required=True)
    source_control_parser.add_argument("--line", "--l", dest="line", action="store_true")
    source_control_parser.add_argument("--ble-source", "--b", dest="ble_source", action="store_true")
    source_control_parser.add_argument("--digital", "--d", dest="digital", action="store_true")
    source_control_parser.add_argument("--mask", type=lambda value: int(value, 0))
    source_control_parser.add_argument("--send", action="store_true")
    source_control_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(source_control_parser)
    source_control_parser.set_defaults(handler=lambda args: asyncio.run(_run_source_control(args)))

    mute_control_parser = subparsers.add_parser("mute", help="Set per-channel mute state")
    mute_control_parser.add_argument("--config", default="examples/fa860.example.json")
    mute_control_parser.add_argument("--channel", "--ch", dest="channel", type=int, required=True)
    mute_control_parser.add_argument("--mute", dest="mute", action="store_true")
    mute_control_parser.add_argument("--unmute", dest="mute", action="store_false")
    mute_control_parser.set_defaults(mute=True)
    mute_control_parser.add_argument("--send", action="store_true")
    mute_control_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(mute_control_parser)
    mute_control_parser.set_defaults(handler=lambda args: asyncio.run(_run_mute_control(args)))

    volume_control_parser = subparsers.add_parser("volume", help="Set per-channel volume in dB")
    volume_control_parser.add_argument("--config", default="examples/fa860.example.json")
    volume_control_parser.add_argument("--channel", "--ch", dest="channel", type=int, required=True)
    volume_control_parser.add_argument("--db", type=int, required=True)
    volume_control_parser.add_argument("--mute", dest="mute", action="store_true")
    volume_control_parser.add_argument("--unmute", dest="mute", action="store_false")
    volume_control_parser.set_defaults(mute=False)
    volume_control_parser.add_argument("--send", action="store_true")
    volume_control_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(volume_control_parser)
    volume_control_parser.set_defaults(handler=lambda args: asyncio.run(_run_volume_control(args)))

    source_parser = subparsers.add_parser("experimental-source", help="Build or send an experimental source bitmask HID frame")
    source_parser.add_argument("--config", default="examples/fa860.example.json")
    source_parser.add_argument("--line", "--l", dest="line", action="store_true")
    source_parser.add_argument("--ble-source", "--b", dest="ble_source", action="store_true")
    source_parser.add_argument("--digital", "--d", dest="digital", action="store_true")
    source_parser.add_argument("--mask", type=lambda value: int(value, 0))
    source_parser.add_argument("--channel", "--ch", dest="channel", type=int)
    source_parser.add_argument("--frame-family", choices=["a1", "a2"], default="a2")
    source_parser.add_argument("--send", action="store_true")
    source_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(source_parser)
    source_parser.set_defaults(handler=lambda args: asyncio.run(_run_experimental_source(args)))

    mute_parser = subparsers.add_parser("experimental-mute", help="Build or send an experimental mute HID frame")
    mute_parser.add_argument("--config", default="examples/fa860.example.json")
    mute_parser.add_argument("--channel", "--ch", dest="channel", type=int)
    mute_parser.add_argument("--target-value", type=lambda value: int(value, 0))
    mute_parser.add_argument("--frame-family", choices=["a1", "a2"], default="a1")
    mute_parser.add_argument("--mute", dest="mute", action="store_true")
    mute_parser.add_argument("--unmute", dest="mute", action="store_false")
    mute_parser.set_defaults(mute=True)
    mute_parser.add_argument("--send", action="store_true")
    mute_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(mute_parser)
    mute_parser.set_defaults(handler=lambda args: asyncio.run(_run_experimental_mute(args)))

    volume_parser = subparsers.add_parser("experimental-volume", help="Build or send an experimental volume HID frame")
    volume_parser.add_argument("--config", default="examples/fa860.example.json")
    volume_parser.add_argument("--channel", "--ch", dest="channel", type=int, required=True)
    volume_parser.add_argument("--db", type=int, required=True)
    volume_parser.add_argument("--target-value", type=lambda value: int(value, 0))
    volume_parser.add_argument("--mute", dest="mute", action="store_true")
    volume_parser.add_argument("--unmute", dest="mute", action="store_false")
    volume_parser.set_defaults(mute=False)
    volume_parser.add_argument("--send", action="store_true")
    volume_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(volume_parser)
    volume_parser.set_defaults(handler=lambda args: asyncio.run(_run_experimental_volume(args)))

    mixer_parser = subparsers.add_parser("experimental-mix-block", help="Build or send an experimental eight-value mixer HID block frame")
    mixer_parser.add_argument("--config", default="examples/fa860.example.json")
    mixer_parser.add_argument("--channel", "--ch", dest="channel", type=int, required=True)
    mixer_parser.add_argument("--block", type=int, default=1)
    mixer_parser.add_argument("--opcode", type=lambda value: int(value, 0), default=MIXER_LINE_OPCODE)
    mixer_parser.add_argument("--index", type=int)
    mixer_parser.add_argument("--values", type=int, nargs=8, metavar=("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"), required=True)
    mixer_parser.add_argument("--derived-seed", type=lambda value: int(value, 0))
    mixer_parser.add_argument("--parse", action="store_true")
    mixer_parser.add_argument("--send", action="store_true")
    mixer_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(mixer_parser)
    mixer_parser.set_defaults(handler=lambda args: asyncio.run(_run_experimental_mixer_block(args)))

    mixer_tail_parser = subparsers.add_parser("mix-tail", help="Set per-channel DIGITAL_L, DIGITAL_R, BT_L, BT_R mixer levels")
    mixer_tail_parser.add_argument("--config", default="examples/fa860.example.json")
    mixer_tail_parser.add_argument("--channel", "--ch", dest="channel", type=int, required=True)
    mixer_tail_parser.add_argument("--digital-l", type=int, required=True)
    mixer_tail_parser.add_argument("--digital-r", type=int, required=True)
    mixer_tail_parser.add_argument("--bt-l", type=int, required=True)
    mixer_tail_parser.add_argument("--bt-r", type=int, required=True)
    mixer_tail_parser.add_argument("--derived-seed", type=lambda value: int(value, 0))
    mixer_tail_parser.add_argument("--parse", action="store_true")
    mixer_tail_parser.add_argument("--send", action="store_true")
    mixer_tail_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(mixer_tail_parser)
    mixer_tail_parser.set_defaults(handler=lambda args: asyncio.run(_run_mixer_tail(args)))

    mixer_line_parser = subparsers.add_parser("mix-line", help="Set per-channel LINE1..LINE8 mixer levels")
    mixer_line_parser.add_argument("--config", default="examples/fa860.example.json")
    mixer_line_parser.add_argument("--channel", "--ch", dest="channel", type=int, required=True)
    mixer_line_parser.add_argument("--values", type=int, nargs=8, metavar=("LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8"), required=True)
    mixer_line_parser.add_argument("--derived-seed", type=lambda value: int(value, 0))
    mixer_line_parser.add_argument("--parse", action="store_true")
    mixer_line_parser.add_argument("--send", action="store_true")
    mixer_line_parser.add_argument("--read-size", type=int, default=0)
    add_transport_args(mixer_line_parser)
    mixer_line_parser.set_defaults(handler=lambda args: asyncio.run(_run_mixer_line(args)))

    args = parser.parse_args()
    if args.subcommand is None:
        if _is_direct_control_request(args):
            asyncio.run(_run_direct_control(args))
            return
        parser.error("a subcommand is required unless you use direct control flags like --channel 1 --mute")
    args.handler(args)


def _is_direct_control_request(args: argparse.Namespace) -> bool:
    has_source_flags = args.line or args.ble_source or args.digital
    return args.channel is not None and (
        args.direct_mute is not None
        or args.db is not None
        or has_source_flags
        or args.mix_line is not None
        or args.mix_tail is not None
    )


def _build_direct_operations(args: argparse.Namespace) -> list[tuple[str, bytes]]:
    operations: list[tuple[str, bytes]] = []
    if args.line or args.ble_source or args.digital:
        source_mask = build_source_mask(line=args.line, ble=args.ble_source, digital=args.digital)
        operations.append(("source", build_source_control_frame(source_mask, channel=args.channel)))
    if args.db is not None:
        operations.append(("volume", build_volume_control_frame(channel=args.channel, db=args.db, mute=False if args.direct_mute is None else args.direct_mute)))
    elif args.direct_mute is not None:
        operations.append(("mute", build_mute_control_frame(channel=args.channel, mute=args.direct_mute)))
    if args.mix_line is not None:
        operations.append(("mix-line", build_mixer_line_control_frame(channel=args.channel, values=tuple(args.mix_line))))
    if args.mix_tail is not None:
        digital_l, digital_r, bt_l, bt_r = args.mix_tail
        operations.append((
            "mix-tail",
            build_mixer_tail_control_frame(
                channel=args.channel,
                digital_l=digital_l,
                digital_r=digital_r,
                bt_l=bt_l,
                bt_r=bt_r,
            ),
        ))
    return operations


async def _run_direct_control(args: argparse.Namespace) -> None:
    operations = _build_direct_operations(args)
    if not operations:
        raise ValueError("no direct control operation specified")
    transport = build_transport(args)
    config = load_protocol_config(args.config)
    async with FA860Client(transport, config) as client:
        for name, payload in operations:
            print(f"{name}: {bytes_to_hex(payload)}")
            response = await client.send_frame(payload, read_size=args.read_size)
            if response:
                print(bytes_to_hex(response))


async def _scan_ble_command() -> None:
    for device in await scan_ble():
        print(f"{device.address}\t{device.name or ''}")


def _list_hid_devices() -> None:
    for device in list_hid_devices():
        print(json.dumps(device, ensure_ascii=False))


def _list_setupapi_hid(args: argparse.Namespace) -> None:
    for device in enumerate_hid_interfaces(vid=args.vendor_id, pid=args.product_id):
        print(json.dumps(device, ensure_ascii=False))


async def _run_experimental_source(args: argparse.Namespace) -> None:
    mask = args.mask
    if mask is None:
        mask = build_source_mask(line=args.line, ble=args.ble_source, digital=args.digital)
    payload = build_source_frame(mask, frame_family=args.frame_family, channel=args.channel)
    await run_experimental_frame(args, payload)


async def _run_source_control(args: argparse.Namespace) -> None:
    mask = args.mask
    if mask is None:
        mask = build_source_mask(line=args.line, ble=args.ble_source, digital=args.digital)
    payload = build_source_control_frame(mask, channel=args.channel)
    await run_experimental_frame(args, payload)


async def _run_experimental_mute(args: argparse.Namespace) -> None:
    if args.target_value is not None:
        target_value = args.target_value
    elif args.channel is not None:
        target_value = observed_mute_target(args.channel)
    else:
        raise ValueError("experimental-mute requires --channel or --target-value")
    payload = build_mute_frame(target_value=target_value, mute=args.mute, frame_family=args.frame_family, channel=args.channel)
    await run_experimental_frame(args, payload)


async def _run_mute_control(args: argparse.Namespace) -> None:
    payload = build_mute_control_frame(channel=args.channel, mute=args.mute)
    await run_experimental_frame(args, payload)


async def _run_experimental_volume(args: argparse.Namespace) -> None:
    target_value = args.target_value
    if target_value is None:
        target_value = observed_mute_target(args.channel)
    payload = build_a1_volume_frame(db=args.db, mute=args.mute, channel=args.channel, target_value=target_value)
    await run_experimental_frame(args, payload)


async def _run_volume_control(args: argparse.Namespace) -> None:
    payload = build_volume_control_frame(channel=args.channel, db=args.db, mute=args.mute)
    await run_experimental_frame(args, payload)


async def _run_experimental_mixer_block(args: argparse.Namespace) -> None:
    index = args.block if args.index is None else args.index
    if args.opcode == MIXER_LINE_OPCODE:
        payload = build_mixer_block_control_frame(
            channel=args.channel,
            block=index,
            values=tuple(args.values),
            derived_seed=args.derived_seed,
        )
    elif args.opcode == MIXER_AUX_OPCODE:
        payload = build_a1_mixer_aux_frame(
            channel=args.channel,
            values=tuple(args.values),
            derived_seed=args.derived_seed,
        )
    else:
        payload = build_a1_mixer_frame(
            channel=args.channel,
            opcode=args.opcode,
            index=index,
            values=tuple(args.values),
            derived_seed=args.derived_seed,
        )
    labels = None
    try:
        labels = mixer_section_labels(args.opcode, index)
    except ValueError:
        if args.opcode == MIXER_LINE_OPCODE:
            labels = mixer_block_labels(index)
    if labels is not None:
        print(f"labels: {', '.join(labels)}")
    if args.parse:
        print(json.dumps(parse_a1_mixer_block_frame(payload), ensure_ascii=False))
    await run_experimental_frame(args, payload)


async def _run_mixer_tail(args: argparse.Namespace) -> None:
    payload = build_mixer_tail_control_frame(
        channel=args.channel,
        digital_l=args.digital_l,
        digital_r=args.digital_r,
        bt_l=args.bt_l,
        bt_r=args.bt_r,
        derived_seed=args.derived_seed,
    )
    print("labels: DIGITAL_L, DIGITAL_R, BT_L, BT_R")
    if args.parse:
        print(json.dumps(parse_a1_mixer_block_frame(payload), ensure_ascii=False))
    await run_experimental_frame(args, payload)


async def _run_mixer_line(args: argparse.Namespace) -> None:
    payload = build_mixer_line_control_frame(
        channel=args.channel,
        values=tuple(args.values),
        derived_seed=args.derived_seed,
    )
    print("labels: LINE1, LINE2, LINE3, LINE4, LINE5, LINE6, LINE7, LINE8")
    if args.parse:
        print(json.dumps(parse_a1_mixer_block_frame(payload), ensure_ascii=False))
    await run_experimental_frame(args, payload)


if __name__ == "__main__":
    main()
