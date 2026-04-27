from fa860_control.protocol import apply_checksum, bytes_to_hex, hex_to_bytes, render_request


def test_hex_roundtrip() -> None:
    payload = hex_to_bytes("AA 55 02 01")
    assert bytes_to_hex(payload) == "AA 55 02 01"


def test_render_request() -> None:
    payload = render_request("AA 55 02 01 {volume:02X}", {"volume": 35})
    assert bytes_to_hex(payload) == "AA 55 02 01 23"


def test_sum8_checksum() -> None:
    payload = hex_to_bytes("01 02 03")
    checksummed = apply_checksum(payload, "sum8", True)
    assert bytes_to_hex(checksummed) == "01 02 03 06"
