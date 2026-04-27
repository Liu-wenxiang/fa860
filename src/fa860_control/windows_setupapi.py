from __future__ import annotations

import ctypes
from ctypes import wintypes

from .transports.hid_transport import list_hid_devices


if ctypes.sizeof(ctypes.c_void_p) == 8:
    _DETAIL_CB_SIZE = 8
else:
    _DETAIL_CB_SIZE = 6


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class SP_DEVICE_INTERFACE_DETAIL_DATA_W(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("DevicePath", wintypes.WCHAR * 1),
    ]


DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
DEFAULT_FA860_VENDOR_ID = 0x0483
DEFAULT_FA860_PRODUCT_ID = 0x5750


def _require_windows() -> None:
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("SetupAPI enumeration is only available on Windows")


def enumerate_hid_interfaces(vid: int | None = None, pid: int | None = None) -> list[dict[str, str]]:
    _require_windows()

    setupapi = ctypes.windll.setupapi
    hid_dll = ctypes.windll.hid

    setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
    setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
    setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(SP_DEVINFO_DATA)]
    setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.LPWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    setupapi.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

    hid_guid = GUID()
    hid_dll.HidD_GetHidGuid(ctypes.byref(hid_guid))

    device_info_set = setupapi.SetupDiGetClassDevsW(
        ctypes.byref(hid_guid),
        None,
        None,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE,
    )
    if device_info_set == INVALID_HANDLE_VALUE:
        raise ctypes.WinError()

    results: list[dict[str, str]] = []

    try:
        index = 0
        while True:
            interface_data = SP_DEVICE_INTERFACE_DATA()
            interface_data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)

            success = setupapi.SetupDiEnumDeviceInterfaces(
                device_info_set,
                None,
                ctypes.byref(hid_guid),
                index,
                ctypes.byref(interface_data),
            )
            if not success:
                error = ctypes.GetLastError()
                if error == 259:
                    break
                raise ctypes.WinError(error)

            required_size = wintypes.DWORD()
            devinfo_data = SP_DEVINFO_DATA()
            devinfo_data.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)

            setupapi.SetupDiGetDeviceInterfaceDetailW(
                device_info_set,
                ctypes.byref(interface_data),
                None,
                0,
                ctypes.byref(required_size),
                ctypes.byref(devinfo_data),
            )

            buffer = ctypes.create_string_buffer(required_size.value)
            detail = ctypes.cast(buffer, ctypes.POINTER(SP_DEVICE_INTERFACE_DETAIL_DATA_W))
            detail.contents.cbSize = _DETAIL_CB_SIZE

            success = setupapi.SetupDiGetDeviceInterfaceDetailW(
                device_info_set,
                ctypes.byref(interface_data),
                detail,
                required_size,
                ctypes.byref(required_size),
                ctypes.byref(devinfo_data),
            )
            if not success:
                raise ctypes.WinError()

            device_path = ctypes.wstring_at(ctypes.addressof(buffer) + ctypes.sizeof(wintypes.DWORD))

            instance_id_buffer = ctypes.create_unicode_buffer(512)
            success = setupapi.SetupDiGetDeviceInstanceIdW(
                device_info_set,
                ctypes.byref(devinfo_data),
                instance_id_buffer,
                len(instance_id_buffer),
                None,
            )
            if not success:
                raise ctypes.WinError()

            path_lower = device_path.lower()
            if vid is not None and f"vid_{vid:04x}" not in path_lower:
                index += 1
                continue
            if pid is not None and f"pid_{pid:04x}" not in path_lower:
                index += 1
                continue

            results.append(
                {
                    "path": device_path,
                    "instance_id": instance_id_buffer.value,
                }
            )
            index += 1
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(device_info_set)

    return results


def select_hid_path(devices: list[dict[str, str]], *, vid: int, pid: int) -> str:
    if not devices:
        raise RuntimeError(f"no HID interface found for VID 0x{vid:04X} PID 0x{pid:04X}")
    if len(devices) > 1:
        paths = ", ".join(device["path"] for device in devices)
        raise RuntimeError(
            f"multiple HID interfaces found for VID 0x{vid:04X} PID 0x{pid:04X}; "
            f"specify --hid-path explicitly. Paths: {paths}"
        )
    return devices[0]["path"]


def resolve_hid_path(path: str | None = None, *, vid: int | None = None, pid: int | None = None) -> str:
    if path:
        return path
    resolved_vid = DEFAULT_FA860_VENDOR_ID if vid is None else vid
    resolved_pid = DEFAULT_FA860_PRODUCT_ID if pid is None else pid
    if hasattr(ctypes, "windll"):
        devices = enumerate_hid_interfaces(vid=resolved_vid, pid=resolved_pid)
    else:
        devices = [
            {"path": str(device["path"]), "instance_id": str(device.get("serial_number") or "")}
            for device in list_hid_devices()
            if device.get("vendor_id") == resolved_vid and device.get("product_id") == resolved_pid and device.get("path")
        ]
    return select_hid_path(devices, vid=resolved_vid, pid=resolved_pid)
