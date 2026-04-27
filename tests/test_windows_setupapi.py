import pytest

from fa860_control import windows_setupapi
from fa860_control.windows_setupapi import _DETAIL_CB_SIZE, resolve_hid_path, select_hid_path


def test_detail_cb_size() -> None:
    assert _DETAIL_CB_SIZE in {6, 8}


def test_select_hid_path_returns_only_path() -> None:
    path = select_hid_path([
        {"path": "\\\\?\\hid#vid_0483&pid_5750#foo", "instance_id": "USB\\VID_0483&PID_5750\\1"}
    ], vid=0x0483, pid=0x5750)
    assert path == "\\\\?\\hid#vid_0483&pid_5750#foo"


def test_select_hid_path_errors_when_missing() -> None:
    with pytest.raises(RuntimeError, match="no HID interface found"):
        select_hid_path([], vid=0x0483, pid=0x5750)


def test_select_hid_path_errors_when_multiple() -> None:
    with pytest.raises(RuntimeError, match="multiple HID interfaces found"):
        select_hid_path(
            [
                {"path": "path-a", "instance_id": "a"},
                {"path": "path-b", "instance_id": "b"},
            ],
            vid=0x0483,
            pid=0x5750,
        )


def test_resolve_hid_path_uses_non_windows_hid_enumeration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(windows_setupapi.ctypes, "windll", raising=False)
    monkeypatch.setattr(
        windows_setupapi,
        "list_hid_devices",
        lambda: [
            {
                "path": "/dev/hidraw3",
                "vendor_id": 0x0483,
                "product_id": 0x5750,
                "serial_number": "fa860",
            }
        ],
    )

    path = resolve_hid_path(vid=0x0483, pid=0x5750)
    assert path == "/dev/hidraw3"