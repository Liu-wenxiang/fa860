from __future__ import annotations

FRAME_SIZE = 64
MIXER_BLOCK_COUNT = 2
MIXER_BLOCK_SIZE = 8
MIXER_LINE_OPCODE = 0x21
MIXER_AUX_OPCODE = 0x22

A1_SOURCE_FRAME_PREFIX = bytes.fromhex(
    "91 91 91 EE A1 01 00 04"
)

A2_SOURCE_FRAME_PREFIX = bytes.fromhex(
    "91 91 91 EE A2 01 00 09 03 00 00 00 08 00 A4 01 14 00 14 00 01"
)

A1_MUTE_FRAME_PREFIX = bytes.fromhex(
    "91 91 91 EE A1 01 00 04"
)

A2_MUTE_FRAME_PREFIX = bytes.fromhex(
    "91 91 91 EE A2 01 00 09 03 00 00 00 08 00"
)

OBSERVED_MUTE_TARGETS = {
    1: 0x01,
    2: 0x05,
    3: 0x07,
    4: 0x0B,
    5: 0x15,
    6: 0x12,
    7: 0x15,
    8: 0x18,
}

MIXER_BLOCK_LABELS = {
    1: ("LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8"),
    2: ("SLOT1", "SLOT2", "SLOT3", "SLOT4", "SLOT5", "SLOT6", "SLOT7", "SLOT8"),
}

MIXER_SECTION_LABELS = {
    (MIXER_LINE_OPCODE, 1): ("LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8"),
    (MIXER_AUX_OPCODE, 0): ("PREFIX1", "PREFIX2", "PREFIX3", "PREFIX4", "DIGITAL_L", "DIGITAL_R", "BT_L", "BT_R"),
}


def channel_target_value(channel: int) -> int:
    if channel not in OBSERVED_MUTE_TARGETS:
        raise ValueError(f"unsupported channel: {channel}")
    return OBSERVED_MUTE_TARGETS[channel]


def mixer_block_labels(block: int) -> tuple[str, ...]:
    if not 1 <= block <= MIXER_BLOCK_COUNT:
        raise ValueError(f"block must be between 1 and {MIXER_BLOCK_COUNT}")
    return MIXER_BLOCK_LABELS[block]


def mixer_section_labels(opcode: int, index: int) -> tuple[str, ...]:
    key = (opcode, index)
    if key not in MIXER_SECTION_LABELS:
        raise ValueError(f"unknown mixer section opcode=0x{opcode:02X}, index={index}")
    return MIXER_SECTION_LABELS[key]


def observed_mixer_derived_seed(channel: int, block: int) -> int:
    if not 1 <= channel <= 8:
        raise ValueError("channel must be between 1 and 8")
    if not 1 <= block <= MIXER_BLOCK_COUNT:
        raise ValueError(f"block must be between 1 and {MIXER_BLOCK_COUNT}")
    return (0x8C + ((block - 1) * 0x10)) ^ (channel - 1)


def observed_mixer_aux_prefix(channel: int) -> tuple[int, int, int, int]:
    if not 1 <= channel <= 8:
        raise ValueError("channel must be between 1 and 8")
    channel_index = channel - 1
    if channel_index % 2 == 0:
        return (0, 0, 100, 0)
    return (0, 0, 0, 100)


def observed_mixer_aux_seed(channel: int) -> int:
    if not 1 <= channel <= 8:
        raise ValueError("channel must be between 1 and 8")
    return 0x8E ^ (channel - 1)


def build_a1_mixer_frame(channel: int, opcode: int, index: int, values: tuple[int, ...], derived_seed: int | None = None) -> bytes:
    if opcode not in (MIXER_LINE_OPCODE, MIXER_AUX_OPCODE):
        raise ValueError(f"unsupported mixer opcode: 0x{opcode:02X}")
    if opcode == MIXER_LINE_OPCODE and derived_seed is None:
        derived_seed = observed_mixer_derived_seed(channel, index)
    if opcode == MIXER_AUX_OPCODE and derived_seed is None:
        derived_seed = observed_mixer_aux_seed(channel)
    if derived_seed is None:
        raise ValueError("derived_seed is required for unresolved mixer sections")
    if not 1 <= channel <= 8:
        raise ValueError("channel must be between 1 and 8")
    if len(values) != MIXER_BLOCK_SIZE:
        raise ValueError(f"values must contain exactly {MIXER_BLOCK_SIZE} items")
    if any(not 0 <= value <= 100 for value in values):
        raise ValueError("mixer values must be between 0 and 100")
    channel_byte = channel - 1
    derived = derived_seed
    for value in values:
        derived ^= value
    payload = A1_SOURCE_FRAME_PREFIX + bytes([
        channel_byte,
        opcode,
        index,
        0x00,
        0x08,
        0x00,
        *values,
        derived,
        0xAA,
    ])
    return _pad_frame(payload)

def _pad_frame(payload: bytes) -> bytes:
    if len(payload) > FRAME_SIZE:
        raise ValueError(f"frame too large: {len(payload)} > {FRAME_SIZE}")
    return payload + bytes(FRAME_SIZE - len(payload))


def build_a1_mixer_block_frame(channel: int, block: int, values: tuple[int, ...], derived_seed: int | None = None) -> bytes:
    return build_a1_mixer_frame(channel=channel, opcode=MIXER_LINE_OPCODE, index=block, values=values, derived_seed=derived_seed)


def build_a1_mixer_aux_frame(channel: int, values: tuple[int, ...], derived_seed: int | None = None) -> bytes:
    return build_a1_mixer_frame(channel=channel, opcode=MIXER_AUX_OPCODE, index=0, values=values, derived_seed=derived_seed)


def build_a1_mixer_aux_tail_frame(channel: int, *, digital_l: int, digital_r: int, bt_l: int, bt_r: int, derived_seed: int | None = None) -> bytes:
    prefix = observed_mixer_aux_prefix(channel)
    if derived_seed is None:
        derived_seed = observed_mixer_aux_seed(channel)
    values = prefix + (digital_l, digital_r, bt_l, bt_r)
    return build_a1_mixer_aux_frame(channel=channel, values=values, derived_seed=derived_seed)


def build_mixer_tail_control_frame(
    channel: int,
    *,
    digital_l: int,
    digital_r: int,
    bt_l: int,
    bt_r: int,
    derived_seed: int | None = None,
) -> bytes:
    return build_a1_mixer_aux_tail_frame(
        channel=channel,
        digital_l=digital_l,
        digital_r=digital_r,
        bt_l=bt_l,
        bt_r=bt_r,
        derived_seed=derived_seed,
    )


def parse_a1_mixer_block_frame(payload: bytes) -> dict[str, object]:
    if len(payload) < 24:
        raise ValueError("payload must contain at least 24 bytes")
    if payload[:8] != A1_SOURCE_FRAME_PREFIX or payload[9] not in (MIXER_LINE_OPCODE, MIXER_AUX_OPCODE):
        raise ValueError("payload is not an A1 mixer frame")
    values = tuple(payload[14:22])
    derived = payload[22]
    opcode = payload[9]
    index = payload[10]
    labels = MIXER_SECTION_LABELS.get((opcode, index), tuple(f"RAW{i}" for i in range(1, MIXER_BLOCK_SIZE + 1)))
    channel = payload[8] + 1
    fixed_prefix_matches = True
    if opcode == MIXER_AUX_OPCODE:
        fixed_prefix_matches = values[:4] == observed_mixer_aux_prefix(channel)
    return {
        "channel": channel,
        "opcode": opcode,
        "index": index,
        "block": index,
        "labels": labels,
        "values": values,
        "fixed_prefix_matches": fixed_prefix_matches,
        "derived": derived,
        "derived_seed_candidate": derived ^ values[0] ^ values[1] ^ values[2] ^ values[3] ^ values[4] ^ values[5] ^ values[6] ^ values[7],
    }


def build_mixer_block_control_frame(channel: int, block: int, values: tuple[int, ...], derived_seed: int | None = None) -> bytes:
    return build_a1_mixer_block_frame(channel=channel, block=block, values=values, derived_seed=derived_seed)


def build_mixer_line_control_frame(channel: int, values: tuple[int, ...], derived_seed: int | None = None) -> bytes:
    return build_mixer_block_control_frame(channel=channel, block=1, values=values, derived_seed=derived_seed)


def build_a1_source_frame(mask: int, channel: int | None = None) -> bytes:
    if not 0 <= mask <= 0x07:
        raise ValueError("source mask must be between 0x00 and 0x07")
    channel_byte = 0x00
    if channel is not None:
        if not 1 <= channel <= 8:
            raise ValueError("channel must be between 1 and 8")
        channel_byte = channel - 1
    derived = mask ^ (0x2B ^ channel_byte)
    payload = A1_SOURCE_FRAME_PREFIX + bytes([
        channel_byte,
        0x23,
        0x00,
        0x00,
        0x08,
        0x00,
        0xA4,
        0x01,
        0x14,
        0x00,
        0x14,
        0x00,
        0x01,
        mask,
        derived,
        0xAA,
    ])
    return _pad_frame(payload)


def build_source_control_frame(mask: int, channel: int) -> bytes:
    return build_a1_source_frame(mask, channel=channel)


def build_a2_source_frame(mask: int) -> bytes:
    if not 0 <= mask <= 0x07:
        raise ValueError("source mask must be between 0x00 and 0x07")
    derived = mask ^ 0x05
    return _pad_frame(A2_SOURCE_FRAME_PREFIX + bytes([mask, derived, 0xAA]))


def build_source_frame(mask: int, frame_family: str = "a2", channel: int | None = None) -> bytes:
    if frame_family == "a1":
        return build_a1_source_frame(mask, channel=channel)
    if frame_family == "a2":
        return build_a2_source_frame(mask)
    raise ValueError(f"unsupported source frame family: {frame_family}")


def build_source_mask(line: bool = False, ble: bool = False, digital: bool = False) -> int:
    return (0x02 if line else 0) | (0x04 if ble else 0) | (0x01 if digital else 0)


def build_a1_mute_frame(target_value: int, mute: bool, channel: int | None = None) -> bytes:
    if not 0 <= target_value <= 0xFF:
        raise ValueError("target value must be between 0x00 and 0xFF")
    channel_byte = 0x00
    if channel is not None:
        if not 1 <= channel <= 8:
            raise ValueError("channel must be between 1 and 8")
        channel_byte = channel - 1
    flag = 0x00 if mute else 0x01
    if mute:
        derived_seed = 0xE8 | (channel_byte ^ 0x01)
    else:
        derived_seed = 0xE8 + channel_byte
    derived = target_value ^ derived_seed
    payload = A1_MUTE_FRAME_PREFIX + bytes([
        channel_byte,
        0x1F,
        0x00,
        0x00,
        0x08,
        0x00,
        flag,
        0x00,
        0x58,
        0x02,
        0x00,
        0x00,
        0x00,
        target_value,
        derived,
        0xAA,
    ])
    return _pad_frame(payload)


def build_mute_control_frame(channel: int, mute: bool) -> bytes:
    return build_a1_mute_frame(channel_target_value(channel), mute=mute, channel=channel)


def build_a2_mute_frame(target_value: int, mute: bool) -> bytes:
    if not 0 <= target_value <= 0xFF:
        raise ValueError("target value must be between 0x00 and 0xFF")
    flag = 0x00 if mute else 0x01
    derived = target_value ^ (0xFB if mute else 0xFA)
    payload = A2_MUTE_FRAME_PREFIX + bytes([
        flag,
        0x00,
        0x58,
        0x02,
        0x00,
        0x00,
        0x00,
        target_value,
        derived,
        0xAA,
    ])
    return _pad_frame(payload)


def build_a1_volume_frame(db: int, mute: bool, channel: int | None = None, target_value: int | None = None) -> bytes:
    if not -60 <= db <= 0:
        raise ValueError("db must be between -60 and 0")
    channel_byte = 0x00
    if channel is not None:
        if not 1 <= channel <= 8:
            raise ValueError("channel must be between 1 and 8")
        channel_byte = channel - 1
    if target_value is None:
        if channel is None:
            raise ValueError("target_value is required when channel is not provided")
        target_value = observed_mute_target(channel)
    if not 0 <= target_value <= 0xFF:
        raise ValueError("target value must be between 0x00 and 0xFF")
    encoded = (db + 60) * 10
    value_lo = encoded & 0xFF
    value_hi = (encoded >> 8) & 0xFF
    flag = 0x00 if mute else 0x01
    seed = 0xB3 if mute else 0xB2
    derived = value_lo ^ value_hi ^ target_value ^ channel_byte ^ seed
    payload = A1_MUTE_FRAME_PREFIX + bytes([
        channel_byte,
        0x1F,
        0x00,
        0x00,
        0x08,
        0x00,
        flag,
        0x00,
        value_lo,
        value_hi,
        0x00,
        0x00,
        0x00,
        target_value,
        derived,
        0xAA,
    ])
    return _pad_frame(payload)


def build_volume_control_frame(channel: int, db: int, mute: bool = False) -> bytes:
    return build_a1_volume_frame(db=db, mute=mute, channel=channel, target_value=channel_target_value(channel))


def build_mute_frame(target_value: int, mute: bool, frame_family: str = "a1", channel: int | None = None) -> bytes:
    if frame_family == "a1":
        return build_a1_mute_frame(target_value, mute, channel=channel)
    if frame_family == "a2":
        return build_a2_mute_frame(target_value, mute)
    raise ValueError(f"unsupported mute frame family: {frame_family}")


def observed_mute_target(channel: int) -> int:
    return channel_target_value(channel)
