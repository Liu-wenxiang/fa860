from fa860_control.experimental import MIXER_AUX_OPCODE, MIXER_LINE_OPCODE, build_a1_mixer_aux_frame, build_a1_mixer_aux_tail_frame, build_a1_mixer_block_frame, build_a1_mixer_frame, build_a1_mute_frame, build_a1_source_frame, build_a1_volume_frame, build_a2_mute_frame, build_a2_source_frame, build_mixer_block_control_frame, build_mixer_line_control_frame, build_mixer_tail_control_frame, build_mute_control_frame, build_mute_frame, build_source_control_frame, build_source_frame, build_source_mask, build_volume_control_frame, mixer_block_labels, mixer_section_labels, observed_mixer_aux_prefix, observed_mixer_aux_seed, observed_mute_target, observed_mixer_derived_seed, parse_a1_mixer_block_frame
from fa860_control.protocol import bytes_to_hex


def test_build_source_mask() -> None:
    assert build_source_mask(line=True, ble=True, digital=False) == 0x06


def test_mixer_block_labels() -> None:
    assert mixer_block_labels(1) == ("LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8")
    assert mixer_block_labels(2) == ("SLOT1", "SLOT2", "SLOT3", "SLOT4", "SLOT5", "SLOT6", "SLOT7", "SLOT8")


def test_observed_mixer_derived_seed() -> None:
    assert observed_mixer_derived_seed(1, 1) == 0x8C
    assert observed_mixer_derived_seed(2, 1) == 0x8D
    assert observed_mixer_derived_seed(3, 1) == 0x8E
    assert observed_mixer_derived_seed(5, 1) == 0x88
    assert observed_mixer_derived_seed(6, 1) == 0x89
    assert observed_mixer_derived_seed(7, 1) == 0x8A
    assert observed_mixer_derived_seed(8, 1) == 0x8B


def test_mixer_section_labels() -> None:
    assert mixer_section_labels(MIXER_LINE_OPCODE, 1) == ("LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8")
    assert mixer_section_labels(MIXER_AUX_OPCODE, 0) == ("PREFIX1", "PREFIX2", "PREFIX3", "PREFIX4", "DIGITAL_L", "DIGITAL_R", "BT_L", "BT_R")


def test_observed_mixer_aux_prefix_and_seed() -> None:
    assert observed_mixer_aux_prefix(1) == (0, 0, 100, 0)
    assert observed_mixer_aux_prefix(2) == (0, 0, 0, 100)
    assert observed_mixer_aux_prefix(3) == (0, 0, 100, 0)
    assert observed_mixer_aux_prefix(8) == (0, 0, 0, 100)
    assert observed_mixer_aux_seed(1) == 0x8E
    assert observed_mixer_aux_seed(2) == 0x8F
    assert observed_mixer_aux_seed(3) == 0x8C
    assert observed_mixer_aux_seed(4) == 0x8D
    assert observed_mixer_aux_seed(5) == 0x8A
    assert observed_mixer_aux_seed(6) == 0x8B
    assert observed_mixer_aux_seed(7) == 0x88
    assert observed_mixer_aux_seed(8) == 0x89


def test_build_a1_mixer_block_frame_for_ch1_line2_on() -> None:
    payload = build_a1_mixer_block_frame(channel=1, block=1, values=(100, 100, 100, 0, 0, 0, 0, 0))
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 21 01 00 08 00 64 64 64 00 00 00 00 00 E8 AA"


def test_build_mixer_block_control_frame_for_ch1_line2_off() -> None:
    payload = build_mixer_block_control_frame(channel=1, block=1, values=(100, 0, 100, 0, 0, 0, 0, 0))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 21 01 00 08 00 64 00 64 00 00 00 00 00 8C AA"


def test_build_mixer_line_control_frame() -> None:
    payload = build_mixer_line_control_frame(channel=1, values=(100, 0, 100, 0, 0, 0, 0, 0))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 21 01 00 08 00 64 00 64 00 00 00 00 00 8C AA"


def test_build_a1_mixer_block_frame_for_ch1_line3_on() -> None:
    payload = build_a1_mixer_block_frame(channel=1, block=1, values=(0, 0, 100, 0, 0, 0, 0, 0))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 21 01 00 08 00 00 00 64 00 00 00 00 00 E8 AA"


def test_build_a1_mixer_block_frame_for_ch1_all_zero() -> None:
    payload = build_a1_mixer_block_frame(channel=1, block=1, values=(0, 0, 0, 0, 0, 0, 0, 0))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 21 01 00 08 00 00 00 00 00 00 00 00 00 8C AA"


def test_build_a1_mixer_block_frame_for_ch1_line4_on() -> None:
    payload = build_a1_mixer_block_frame(channel=1, block=1, values=(0, 0, 0, 100, 0, 0, 0, 0))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 21 01 00 08 00 00 00 00 64 00 00 00 00 E8 AA"


def test_build_a1_mixer_block_frame_for_ch2_line8_on() -> None:
    payload = build_a1_mixer_block_frame(channel=2, block=1, values=(0, 100, 0, 100, 0, 0, 0, 100))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 01 21 01 00 08 00 00 64 00 64 00 00 00 64 E9 AA"


def test_build_a1_mixer_block_frame_for_ch3_line1_to_8() -> None:
    payload = build_a1_mixer_block_frame(channel=3, block=1, values=(1, 2, 3, 4, 5, 6, 7, 8))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 21 01 00 08 00 01 02 03 04 05 06 07 08 86 AA"


def test_build_a1_mixer_block_frame_for_ch5_official_sample() -> None:
    payload = build_a1_mixer_block_frame(channel=5, block=1, values=(100, 0, 1, 0, 100, 0, 0, 0))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 04 21 01 00 08 00 64 00 01 00 64 00 00 00 89 AA"


def test_build_a1_mixer_block_frame_for_ch6_official_sample() -> None:
    payload = build_a1_mixer_block_frame(channel=6, block=1, values=(0, 100, 1, 0, 0, 100, 0, 0))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 05 21 01 00 08 00 00 64 01 00 00 64 00 00 88 AA"


def test_build_a1_mixer_block_frame_for_ch7_official_sample() -> None:
    payload = build_a1_mixer_block_frame(channel=7, block=1, values=(100, 0, 1, 0, 0, 0, 100, 0))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 06 21 01 00 08 00 64 00 01 00 00 00 64 00 8B AA"


def test_build_a1_mixer_block_frame_for_ch8_official_sample() -> None:
    payload = build_a1_mixer_block_frame(channel=8, block=1, values=(100, 100, 100, 0, 0, 0, 0, 100))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 07 21 01 00 08 00 64 64 64 00 00 00 00 64 8B AA"


def test_build_a1_mixer_block_frame_for_ch8_latest_official_sample() -> None:
    payload = build_a1_mixer_block_frame(channel=8, block=1, values=(100, 100, 1, 0, 0, 0, 0, 100))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 07 21 01 00 08 00 64 64 01 00 00 00 00 64 EE AA"


def test_build_mixer_line_control_frame_for_ch8_latest_official_sample() -> None:
    payload = build_mixer_line_control_frame(channel=8, values=(100, 100, 1, 0, 0, 0, 0, 100))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 07 21 01 00 08 00 64 64 01 00 00 00 00 64 EE AA"


def test_build_a1_mixer_aux_frame_for_ch3_observed_tail_block() -> None:
    payload = build_a1_mixer_aux_frame(channel=3, values=(0, 0, 100, 0, 11, 12, 9, 10), derived_seed=0x8C)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 0B 0C 09 0A EC AA"


def test_build_a1_mixer_aux_tail_frame() -> None:
    payload = build_a1_mixer_aux_tail_frame(channel=3, digital_l=11, digital_r=12, bt_l=9, bt_r=10)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 0B 0C 09 0A EC AA"


def test_build_mixer_tail_control_frame() -> None:
    payload = build_mixer_tail_control_frame(channel=3, digital_l=11, digital_r=12, bt_l=9, bt_r=10)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 0B 0C 09 0A EC AA"


def test_build_a1_mixer_aux_tail_frame_for_ch2_observed_sample() -> None:
    payload = build_a1_mixer_aux_tail_frame(channel=2, digital_l=3, digital_r=4, bt_l=1, bt_r=2)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 01 22 00 00 08 00 00 00 00 64 03 04 01 02 EF AA"


def test_build_a1_mixer_aux_frame_uses_channel_seed_by_default() -> None:
    payload = build_a1_mixer_aux_frame(channel=4, values=(0, 0, 0, 100, 0, 100, 0, 2))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 03 22 00 00 08 00 00 00 00 64 00 64 00 02 8F AA"


def test_build_a1_mixer_aux_tail_frame_for_ch1_observed_sample() -> None:
    payload = build_a1_mixer_aux_tail_frame(channel=1, digital_l=100, digital_r=0, bt_l=100, bt_r=2)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 22 00 00 08 00 00 00 64 00 64 00 64 02 E8 AA"


def test_build_a1_mixer_aux_tail_frame_for_ch4_observed_sample() -> None:
    payload = build_a1_mixer_aux_tail_frame(channel=4, digital_l=0, digital_r=100, bt_l=0, bt_r=2)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 03 22 00 00 08 00 00 00 00 64 00 64 00 02 8F AA"


def test_build_a1_mixer_aux_tail_frame_for_ch5_observed_sample() -> None:
    payload = build_a1_mixer_aux_tail_frame(channel=5, digital_l=100, digital_r=0, bt_l=100, bt_r=2)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 04 22 00 00 08 00 00 00 64 00 64 00 64 02 EC AA"


def test_build_a1_mixer_aux_tail_frame_for_ch6_observed_sample() -> None:
    payload = build_a1_mixer_aux_tail_frame(channel=6, digital_l=0, digital_r=100, bt_l=0, bt_r=2)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 05 22 00 00 08 00 00 00 00 64 00 64 00 02 89 AA"


def test_build_a1_mixer_aux_tail_frame_for_ch7_observed_sample() -> None:
    payload = build_a1_mixer_aux_tail_frame(channel=7, digital_l=100, digital_r=0, bt_l=100, bt_r=2)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 06 22 00 00 08 00 00 00 64 00 64 00 64 02 EE AA"


def test_build_a1_mixer_aux_tail_frame_for_ch8_observed_sample() -> None:
    payload = build_a1_mixer_aux_tail_frame(channel=8, digital_l=0, digital_r=100, bt_l=0, bt_r=2)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 07 22 00 00 08 00 00 00 00 64 00 64 00 02 8B AA"


def test_build_a1_mixer_aux_frame_for_ch3_bt_l_only_changed() -> None:
    payload = build_a1_mixer_aux_frame(channel=3, values=(0, 0, 100, 0, 11, 12, 100, 10), derived_seed=0x8C)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 0B 0C 64 0A 81 AA"


def test_build_a1_mixer_aux_frame_for_ch3_bt_r_only_changed() -> None:
    payload = build_a1_mixer_aux_frame(channel=3, values=(0, 0, 100, 0, 11, 12, 100, 100), derived_seed=0x8C)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 0B 0C 64 64 EF AA"


def test_build_a1_mixer_aux_frame_for_ch3_digital_l_only_changed() -> None:
    payload = build_a1_mixer_aux_frame(channel=3, values=(0, 0, 100, 0, 100, 12, 100, 100), derived_seed=0x8C)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 64 0C 64 64 80 AA"


def test_build_a1_mixer_aux_frame_for_ch3_digital_r_only_changed() -> None:
    payload = build_a1_mixer_aux_frame(channel=3, values=(0, 0, 100, 0, 100, 100, 100, 100), derived_seed=0x8C)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 64 64 64 64 E8 AA"


def test_build_a1_mixer_frame_derives_seed_for_aux_opcode() -> None:
    payload = build_a1_mixer_frame(channel=3, opcode=MIXER_AUX_OPCODE, index=0, values=(0, 0, 100, 0, 11, 12, 9, 10))
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 22 00 00 08 00 00 00 64 00 0B 0C 09 0A EC AA"


def test_parse_a1_mixer_block_frame() -> None:
    payload = build_a1_mixer_block_frame(channel=1, block=1, values=(100, 0, 100, 0, 0, 0, 0, 0))
    parsed = parse_a1_mixer_block_frame(payload)
    assert parsed == {
        "channel": 1,
        "opcode": 0x21,
        "index": 1,
        "block": 1,
        "labels": ("LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8"),
        "values": (100, 0, 100, 0, 0, 0, 0, 0),
        "fixed_prefix_matches": True,
        "derived": 0x8C,
        "derived_seed_candidate": 0x8C,
    }


def test_parse_a1_mixer_aux_frame() -> None:
    payload = build_a1_mixer_aux_frame(channel=3, values=(0, 0, 100, 0, 11, 12, 9, 10), derived_seed=0x8C)
    parsed = parse_a1_mixer_block_frame(payload)
    assert parsed == {
        "channel": 3,
        "opcode": 0x22,
        "index": 0,
        "block": 0,
        "labels": ("PREFIX1", "PREFIX2", "PREFIX3", "PREFIX4", "DIGITAL_L", "DIGITAL_R", "BT_L", "BT_R"),
        "values": (0, 0, 100, 0, 11, 12, 9, 10),
        "fixed_prefix_matches": True,
        "derived": 0xEC,
        "derived_seed_candidate": 0x8C,
    }


def test_parse_a1_mixer_aux_frame_for_ch2() -> None:
    payload = build_a1_mixer_aux_tail_frame(channel=2, digital_l=3, digital_r=4, bt_l=1, bt_r=2)
    parsed = parse_a1_mixer_block_frame(payload)
    assert parsed == {
        "channel": 2,
        "opcode": 0x22,
        "index": 0,
        "block": 0,
        "labels": ("PREFIX1", "PREFIX2", "PREFIX3", "PREFIX4", "DIGITAL_L", "DIGITAL_R", "BT_L", "BT_R"),
        "values": (0, 0, 0, 100, 3, 4, 1, 2),
        "fixed_prefix_matches": True,
        "derived": 0xEF,
        "derived_seed_candidate": 0x8F,
    }


def test_build_a1_source_frame() -> None:
    payload = build_source_frame(0x07, frame_family="a1")
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 23 00 00 08 00 A4 01 14 00 14 00 01 07 2C AA"


def test_build_source_control_frame() -> None:
    payload = build_source_control_frame(0x05, channel=1)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 23 00 00 08 00 A4 01 14 00 14 00 01 05 2E AA"


def test_build_a1_source_frame_for_line_off() -> None:
    payload = build_a1_source_frame(0x05, channel=1)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 23 00 00 08 00 A4 01 14 00 14 00 01 05 2E AA"


def test_build_a1_source_frame_for_channel_2_line_off() -> None:
    payload = build_a1_source_frame(0x05, channel=2)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 01 23 00 00 08 00 A4 01 14 00 14 00 01 05 2F AA"


def test_build_a1_source_frame_for_channel_2_all_on() -> None:
    payload = build_a1_source_frame(0x07, channel=2)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 01 23 00 00 08 00 A4 01 14 00 14 00 01 07 2D AA"


def test_build_a1_source_frame_for_channel_3_line_off() -> None:
    payload = build_a1_source_frame(0x05, channel=3)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 23 00 00 08 00 A4 01 14 00 14 00 01 05 2C AA"


def test_build_a1_source_frame_for_channel_3_all_on() -> None:
    payload = build_a1_source_frame(0x07, channel=3)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 23 00 00 08 00 A4 01 14 00 14 00 01 07 2E AA"


def test_build_a1_source_frame_for_channel_4_line_off() -> None:
    payload = build_a1_source_frame(0x05, channel=4)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 03 23 00 00 08 00 A4 01 14 00 14 00 01 05 2D AA"


def test_build_a1_source_frame_for_channel_4_all_on() -> None:
    payload = build_a1_source_frame(0x07, channel=4)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 03 23 00 00 08 00 A4 01 14 00 14 00 01 07 2F AA"


def test_build_a1_source_frame_for_ble_off() -> None:
    payload = build_a1_source_frame(0x03, channel=1)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 23 00 00 08 00 A4 01 14 00 14 00 01 03 28 AA"


def test_build_a1_source_frame_for_digital_off() -> None:
    payload = build_a1_source_frame(0x06, channel=1)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 23 00 00 08 00 A4 01 14 00 14 00 01 06 2D AA"


def test_build_a2_source_frame() -> None:
    payload = build_source_frame(0x07)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A2 01 00 09 03 00 00 00 08 00 A4 01 14 00 14 00 01 07 02 AA"


def test_build_a1_mute_frame_for_mute() -> None:
    payload = build_a1_mute_frame(0x01, mute=True, channel=1)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 1F 00 00 08 00 00 00 58 02 00 00 00 01 E8 AA"


def test_build_mute_control_frame() -> None:
    payload = build_mute_control_frame(channel=1, mute=True)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 1F 00 00 08 00 00 00 58 02 00 00 00 01 E8 AA"


def test_build_a1_mute_frame_for_unmute() -> None:
    payload = build_a1_mute_frame(0x01, mute=False, channel=1)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 1F 00 00 08 00 01 00 58 02 00 00 00 01 E9 AA"


def test_build_a1_mute_frame_for_channel_2() -> None:
    payload = build_a1_mute_frame(0x05, mute=True, channel=2)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 01 1F 00 00 08 00 00 00 58 02 00 00 00 05 ED AA"


def test_build_a1_mute_frame_for_channel_3() -> None:
    payload = build_a1_mute_frame(0x07, mute=True, channel=3)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 1F 00 00 08 00 00 00 58 02 00 00 00 07 EC AA"


def test_build_a1_unmute_frame_for_channel_3() -> None:
    payload = build_a1_mute_frame(0x07, mute=False, channel=3)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 02 1F 00 00 08 00 01 00 58 02 00 00 00 07 ED AA"


def test_build_a1_mute_frame_for_channel_4() -> None:
    payload = build_a1_mute_frame(0x0B, mute=True, channel=4)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 03 1F 00 00 08 00 00 00 58 02 00 00 00 0B E1 AA"


def test_build_a1_unmute_frame_for_channel_4() -> None:
    payload = build_a1_mute_frame(0x0B, mute=False, channel=4)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 03 1F 00 00 08 00 01 00 58 02 00 00 00 0B E0 AA"


def test_build_a1_mute_frame_for_channel_5() -> None:
    payload = build_a1_mute_frame(0x15, mute=True, channel=5)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 04 1F 00 00 08 00 00 00 58 02 00 00 00 15 F8 AA"


def test_build_a1_unmute_frame_for_channel_5() -> None:
    payload = build_a1_mute_frame(0x15, mute=False, channel=5)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 04 1F 00 00 08 00 01 00 58 02 00 00 00 15 F9 AA"


def test_build_a1_mute_frame_for_channel_6() -> None:
    payload = build_a1_mute_frame(0x12, mute=True, channel=6)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 05 1F 00 00 08 00 00 00 58 02 00 00 00 12 FE AA"


def test_build_a1_unmute_frame_for_channel_6() -> None:
    payload = build_a1_mute_frame(0x12, mute=False, channel=6)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 05 1F 00 00 08 00 01 00 58 02 00 00 00 12 FF AA"


def test_build_a1_mute_frame_for_channel_7() -> None:
    payload = build_a1_mute_frame(0x15, mute=True, channel=7)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 06 1F 00 00 08 00 00 00 58 02 00 00 00 15 FA AA"


def test_build_a1_unmute_frame_for_channel_7() -> None:
    payload = build_a1_mute_frame(0x15, mute=False, channel=7)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 06 1F 00 00 08 00 01 00 58 02 00 00 00 15 FB AA"


def test_build_a1_mute_frame_for_channel_8() -> None:
    payload = build_a1_mute_frame(0x18, mute=True, channel=8)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 07 1F 00 00 08 00 00 00 58 02 00 00 00 18 F6 AA"


def test_build_a1_unmute_frame_for_channel_8() -> None:
    payload = build_a1_mute_frame(0x18, mute=False, channel=8)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 07 1F 00 00 08 00 01 00 58 02 00 00 00 18 F7 AA"


def test_build_a1_volume_frame_for_channel_1_minus_10_mute() -> None:
    payload = build_a1_volume_frame(-10, mute=True, channel=1)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 1F 00 00 08 00 00 00 F4 01 00 00 00 01 47 AA"


def test_build_volume_control_frame() -> None:
    payload = build_volume_control_frame(channel=2, db=-20)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 01 1F 00 00 08 00 01 00 90 01 00 00 00 05 27 AA"


def test_build_a1_volume_frame_for_channel_1_minus_10_unmute() -> None:
    payload = build_a1_volume_frame(-10, mute=False, channel=1)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 1F 00 00 08 00 01 00 F4 01 00 00 00 01 46 AA"


def test_build_a1_volume_frame_for_channel_1_minus_9_unmute() -> None:
    payload = build_a1_volume_frame(-9, mute=False, channel=1)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 1F 00 00 08 00 01 00 FE 01 00 00 00 01 4C AA"


def test_build_a1_volume_frame_for_channel_2_minus_15_unmute() -> None:
    payload = build_a1_volume_frame(-15, mute=False, channel=2)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 01 1F 00 00 08 00 01 00 C2 01 00 00 00 05 75 AA"


def test_build_a2_mute_frame_for_mute() -> None:
    payload = build_a2_mute_frame(0x05, mute=True)
    assert len(payload) == 64
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A2 01 00 09 03 00 00 00 08 00 00 00 58 02 00 00 00 05 FE AA"


def test_build_mute_frame_defaults_to_a1() -> None:
    payload = build_mute_frame(0x01, mute=False, channel=1)
    assert bytes_to_hex(payload[:24]) == "91 91 91 EE A1 01 00 04 00 1F 00 00 08 00 01 00 58 02 00 00 00 01 E9 AA"


def test_observed_mute_targets() -> None:
    assert observed_mute_target(1) == 0x01
    assert observed_mute_target(8) == 0x18