from __future__ import annotations

import re


def normalize_hex(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f{}: ]", "", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.upper()


def hex_to_bytes(value: str) -> bytes:
    normalized = normalize_hex(value).replace(" ", "")
    if len(normalized) % 2 != 0:
        raise ValueError("hex string length must be even")
    return bytes.fromhex(normalized)


def bytes_to_hex(payload: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in payload)


def checksum_sum8(payload: bytes) -> int:
    return sum(payload) & 0xFF


def render_request(template: str, params: dict[str, object]) -> bytes:
    rendered = template.format(**params)
    return hex_to_bytes(rendered)


def apply_checksum(payload: bytes, checksum_name: str | None, enabled: bool) -> bytes:
    if not enabled or not checksum_name:
        return payload
    if checksum_name == "sum8":
        return payload + bytes([checksum_sum8(payload)])
    raise ValueError(f"unsupported checksum: {checksum_name}")
