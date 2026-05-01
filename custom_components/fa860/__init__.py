from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import asyncio
import logging

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "fa860"
CONF_USE_SSL = "use_ssl"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9123
DEFAULT_TIMEOUT = 5.0
PLATFORMS = ("switch", "number")

SERVICE_MUTE = "mute"
SERVICE_SOURCE = "source"
SERVICE_VOLUME = "volume"
SERVICE_MIX_LINE = "mix_line"
SERVICE_MIX_TAIL = "mix_tail"

DATA_CLIENTS = "clients"
DATA_STATES = "states"
DATA_AVAILABILITY = "availability"
DATA_RETRY_UNSUBS = "retry_unsubs"
DATA_UNSUB_STOP = "unsub_stop"
DATA_YAML_CLIENT = "yaml_client"
SIGNAL_STATE_UPDATED = f"{DOMAIN}_state_updated"
SIGNAL_AVAILABILITY_UPDATED = f"{DOMAIN}_availability_updated"
BRIDGE_RETRY_INTERVAL = timedelta(seconds=15)

MIX_LINE_LABELS = ("LINE1", "LINE2", "LINE3", "LINE4", "LINE5", "LINE6", "LINE7", "LINE8")
MIX_TAIL_LABELS = {
    "digital_l": "DIGITAL_L",
    "digital_r": "DIGITAL_R",
    "bt_l": "BT_L",
    "bt_r": "BT_R",
}

_LOGGER = logging.getLogger(__name__)


class Fa860BridgeConnectionError(HomeAssistantError):
    """Raised when Home Assistant cannot reach the FA860 bridge."""


@dataclass(slots=True)
class Fa860ChannelState:
    mute: bool = False
    source_line: bool = True
    source_ble: bool = True
    source_digital: bool = True
    volume_db: int = 0
    mix_line: list[int] = field(default_factory=lambda: [0] * 8)
    mix_tail: dict[str, int] = field(
        default_factory=lambda: {
            "digital_l": 0,
            "digital_r": 0,
            "bt_l": 0,
            "bt_r": 0,
        }
    )

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(float),
                vol.Optional(CONF_USE_SSL, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

MUTE_SCHEMA = vol.Schema(
    {
        vol.Required("channel"): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
        vol.Required("mute"): cv.boolean,
    }
)

SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("channel"): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
        vol.Optional("line", default=False): cv.boolean,
        vol.Optional("ble", default=False): cv.boolean,
        vol.Optional("digital", default=False): cv.boolean,
    }
)

VOLUME_SCHEMA = vol.Schema(
    {
        vol.Required("channel"): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
        vol.Required("db"): vol.All(vol.Coerce(int), vol.Range(min=-60, max=0)),
        vol.Optional("mute", default=False): cv.boolean,
    }
)

MIX_LINE_SCHEMA = vol.Schema(
    {
        vol.Required("channel"): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
        vol.Required("values"): vol.All(
            cv.ensure_list,
            [vol.All(vol.Coerce(int), vol.Range(min=0, max=100))],
            vol.Length(min=8, max=8),
        ),
    }
)

MIX_TAIL_SCHEMA = vol.Schema(
    {
        vol.Required("channel"): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
        vol.Required("digital_l"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Required("digital_r"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Required("bt_l"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Required("bt_r"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
    }
)


@dataclass(slots=True)
class Fa860BridgeClient:
    hass: HomeAssistant
    host: str
    port: int
    timeout: float
    use_ssl: bool

    @property
    def base_url(self) -> str:
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.host}:{self.port}"

    async def async_check_health(self) -> None:
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(self.timeout):
                response = await session.get(f"{self.base_url}/health")
                data = await response.json()
        except (ClientError, OSError, TimeoutError) as exc:
            raise Fa860BridgeConnectionError("Failed to connect to the FA860 bridge") from exc
        if response.status != 200 or not data.get("ok"):
            raise HomeAssistantError("FA860 bridge health check failed")

    async def async_command(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(self.timeout):
                response = await session.post(
                    f"{self.base_url}/command",
                    json={"name": name, "params": params},
                )
                data = await response.json()
        except (ClientError, OSError, TimeoutError) as exc:
            raise Fa860BridgeConnectionError("Failed to connect to the FA860 bridge") from exc
        if response.status >= 400 or not data.get("ok"):
            raise HomeAssistantError(data.get("error", f"FA860 bridge command failed: {response.status}"))
        return data


def _get_default_client(hass: HomeAssistant) -> Fa860BridgeClient:
    domain_data = hass.data.get(DOMAIN, {})
    yaml_client = domain_data.get(DATA_YAML_CLIENT)
    if yaml_client is not None:
        return yaml_client
    clients = domain_data.get(DATA_CLIENTS, {})
    if clients:
        return next(iter(clients.values()))
    raise HomeAssistantError("FA860 integration is not configured")


def _ensure_domain_data(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(
        DOMAIN,
        {
            DATA_CLIENTS: {},
            DATA_STATES: {},
            DATA_AVAILABILITY: {},
            DATA_RETRY_UNSUBS: {},
        },
    )


def _build_channel_states() -> dict[int, Fa860ChannelState]:
    return {channel: Fa860ChannelState() for channel in range(1, 9)}


def _get_default_entry_id(hass: HomeAssistant) -> str | None:
    states = hass.data.get(DOMAIN, {}).get(DATA_STATES, {})
    if states:
        return next(iter(states.keys()))
    return None


def is_entry_available(hass: HomeAssistant, entry_id: str) -> bool:
    return hass.data.get(DOMAIN, {}).get(DATA_AVAILABILITY, {}).get(entry_id, False)


def _set_entry_available(hass: HomeAssistant, entry_id: str, available: bool) -> None:
    domain_data = _ensure_domain_data(hass)
    previous = domain_data[DATA_AVAILABILITY].get(entry_id)
    domain_data[DATA_AVAILABILITY][entry_id] = available
    if previous != available:
        async_dispatcher_send(hass, SIGNAL_AVAILABILITY_UPDATED, entry_id)


def _cancel_retry_poll(hass: HomeAssistant, entry_id: str) -> None:
    unsub = _ensure_domain_data(hass)[DATA_RETRY_UNSUBS].pop(entry_id, None)
    if unsub is not None:
        unsub()


def _schedule_retry_poll(hass: HomeAssistant, entry_id: str) -> None:
    domain_data = _ensure_domain_data(hass)
    if entry_id in domain_data[DATA_RETRY_UNSUBS]:
        return

    async def _async_retry(_: object) -> None:
        client = get_entry_client(hass, entry_id)
        try:
            await client.async_check_health()
        except HomeAssistantError:
            return

        _cancel_retry_poll(hass, entry_id)
        _set_entry_available(hass, entry_id, True)
        _LOGGER.info("FA860 bridge is reachable again: %s", client.base_url)

    domain_data[DATA_RETRY_UNSUBS][entry_id] = async_track_time_interval(hass, _async_retry, BRIDGE_RETRY_INTERVAL)


def _mark_entry_unavailable(hass: HomeAssistant, entry_id: str, reason: str) -> None:
    client = get_entry_client(hass, entry_id)
    if is_entry_available(hass, entry_id):
        _LOGGER.warning("FA860 bridge became unavailable (%s): %s", reason, client.base_url)
    _set_entry_available(hass, entry_id, False)
    _schedule_retry_poll(hass, entry_id)


async def async_execute_entry_command(hass: HomeAssistant, entry_id: str, name: str, params: dict[str, Any]) -> dict[str, Any]:
    client = get_entry_client(hass, entry_id)
    try:
        result = await client.async_command(name, params)
    except Fa860BridgeConnectionError as exc:
        _mark_entry_unavailable(hass, entry_id, str(exc))
        raise

    _cancel_retry_poll(hass, entry_id)
    _set_entry_available(hass, entry_id, True)
    return result


async def _async_execute_default_command(hass: HomeAssistant, name: str, params: dict[str, Any]) -> None:
    entry_id = _get_default_entry_id(hass)
    if entry_id is None:
        await _get_default_client(hass).async_command(name, params)
        return
    await async_execute_entry_command(hass, entry_id, name, params)


def get_entry_client(hass: HomeAssistant, entry_id: str) -> Fa860BridgeClient:
    try:
        return hass.data[DOMAIN][DATA_CLIENTS][entry_id]
    except KeyError as exc:
        raise HomeAssistantError("FA860 integration entry is not available") from exc


def get_channel_state(hass: HomeAssistant, entry_id: str, channel: int) -> Fa860ChannelState:
    try:
        return hass.data[DOMAIN][DATA_STATES][entry_id][channel]
    except KeyError as exc:
        raise HomeAssistantError(f"FA860 channel state is not available for channel {channel}") from exc


def _apply_state_update(state: Fa860ChannelState, name: str, params: dict[str, Any]) -> None:
    if name == SERVICE_MUTE:
        state.mute = bool(params["mute"])
        return
    if name == SERVICE_SOURCE:
        state.source_line = bool(params.get("line", False))
        state.source_ble = bool(params.get("ble", False))
        state.source_digital = bool(params.get("digital", False))
        return
    if name == SERVICE_VOLUME:
        state.volume_db = int(params["db"])
        state.mute = bool(params.get("mute", False))
        return
    if name == SERVICE_MIX_LINE:
        state.mix_line = [int(value) for value in params["values"]]
        return
    if name == SERVICE_MIX_TAIL:
        for key in MIX_TAIL_LABELS:
            state.mix_tail[key] = int(params[key])


def publish_state_update(hass: HomeAssistant, entry_id: str, name: str, params: dict[str, Any]) -> None:
    channel = int(params["channel"])
    state = get_channel_state(hass, entry_id, channel)
    _apply_state_update(state, name, params)
    async_dispatcher_send(hass, SIGNAL_STATE_UPDATED, entry_id, channel)


async def async_send_channel_mute_command(hass: HomeAssistant, entry_id: str, channel: int, mute: bool) -> None:
    if mute:
        params = {"channel": channel, "mute": True}
        await async_execute_entry_command(hass, entry_id, SERVICE_MUTE, params)
        publish_state_update(hass, entry_id, SERVICE_MUTE, params)
        return

    state = get_channel_state(hass, entry_id, channel)
    params = {
        "channel": channel,
        "db": state.volume_db,
        "mute": False,
    }
    await async_execute_entry_command(hass, entry_id, SERVICE_VOLUME, params)
    publish_state_update(hass, entry_id, SERVICE_VOLUME, params)


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_MUTE):
        return

    async def _handle_mute(call: ServiceCall) -> None:
        params = dict(call.data)
        entry_id = _get_default_entry_id(hass)
        if entry_id is None:
            raise HomeAssistantError("FA860 integration is not configured")
        await async_send_channel_mute_command(
            hass,
            entry_id=entry_id,
            channel=int(params["channel"]),
            mute=bool(params["mute"]),
        )

    async def _handle_source(call: ServiceCall) -> None:
        params = dict(call.data)
        await _async_execute_default_command(hass, SERVICE_SOURCE, params)
        entry_id = _get_default_entry_id(hass)
        if entry_id is not None:
            publish_state_update(hass, entry_id, SERVICE_SOURCE, params)

    async def _handle_volume(call: ServiceCall) -> None:
        params = dict(call.data)
        await _async_execute_default_command(hass, SERVICE_VOLUME, params)
        entry_id = _get_default_entry_id(hass)
        if entry_id is not None:
            publish_state_update(hass, entry_id, SERVICE_VOLUME, params)

    async def _handle_mix_line(call: ServiceCall) -> None:
        params = dict(call.data)
        await _async_execute_default_command(hass, SERVICE_MIX_LINE, params)
        entry_id = _get_default_entry_id(hass)
        if entry_id is not None:
            publish_state_update(hass, entry_id, SERVICE_MIX_LINE, params)

    async def _handle_mix_tail(call: ServiceCall) -> None:
        params = dict(call.data)
        await _async_execute_default_command(hass, SERVICE_MIX_TAIL, params)
        entry_id = _get_default_entry_id(hass)
        if entry_id is not None:
            publish_state_update(hass, entry_id, SERVICE_MIX_TAIL, params)

    hass.services.async_register(DOMAIN, SERVICE_MUTE, _handle_mute, schema=MUTE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SOURCE, _handle_source, schema=SOURCE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_VOLUME, _handle_volume, schema=VOLUME_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_MIX_LINE, _handle_mix_line, schema=MIX_LINE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_MIX_TAIL, _handle_mix_tail, schema=MIX_TAIL_SCHEMA)


def _async_unregister_services(hass: HomeAssistant) -> None:
    for service in (SERVICE_MUTE, SERVICE_SOURCE, SERVICE_VOLUME, SERVICE_MIX_LINE, SERVICE_MIX_TAIL):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)


def _ensure_stop_listener(hass: HomeAssistant) -> None:
    domain_data = _ensure_domain_data(hass)
    if domain_data.get(DATA_UNSUB_STOP) is not None:
        return

    async def _handle_stop(_: Any) -> None:
        _async_unregister_services(hass)

    domain_data[DATA_UNSUB_STOP] = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _handle_stop)


def _build_client(hass: HomeAssistant, data: dict[str, Any]) -> Fa860BridgeClient:
    return Fa860BridgeClient(
        hass=hass,
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        timeout=data[CONF_TIMEOUT],
        use_ssl=data[CONF_USE_SSL],
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    _ensure_domain_data(hass)
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    client = _build_client(hass, conf)
    await client.async_check_health()

    domain_data = _ensure_domain_data(hass)
    domain_data[DATA_YAML_CLIENT] = client
    _async_register_services(hass)
    _ensure_stop_listener(hass)
    _LOGGER.info("FA860 bridge integration loaded against %s", client.base_url)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = _ensure_domain_data(hass)
    client = _build_client(hass, entry.data)
    domain_data[DATA_CLIENTS][entry.entry_id] = client
    domain_data[DATA_STATES].setdefault(entry.entry_id, _build_channel_states())
    domain_data[DATA_AVAILABILITY][entry.entry_id] = False

    try:
        await client.async_check_health()
    except HomeAssistantError as exc:
        _LOGGER.warning(
            "FA860 bridge is unavailable during setup, retrying every %s seconds: %s",
            int(BRIDGE_RETRY_INTERVAL.total_seconds()),
            exc,
        )
        _mark_entry_unavailable(hass, entry.entry_id, str(exc))
    else:
        _set_entry_available(hass, entry.entry_id, True)

    _async_register_services(hass)
    _ensure_stop_listener(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = _ensure_domain_data(hass)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        _cancel_retry_poll(hass, entry.entry_id)
        domain_data[DATA_CLIENTS].pop(entry.entry_id, None)
        domain_data[DATA_STATES].pop(entry.entry_id, None)
        domain_data[DATA_AVAILABILITY].pop(entry.entry_id, None)
        if not domain_data[DATA_CLIENTS] and DATA_YAML_CLIENT not in domain_data:
            _async_unregister_services(hass)
    return unload_ok