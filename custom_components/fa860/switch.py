from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, SIGNAL_AVAILABILITY_UPDATED, SIGNAL_STATE_UPDATED, SERVICE_SOURCE, async_execute_entry_command, async_send_channel_mute_command, get_channel_state, is_entry_available, publish_state_update


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    entities: list[SwitchEntity] = []
    for channel in range(1, 9):
        entities.append(Fa860MuteSwitch(hass, entry, channel))
        entities.append(Fa860SourceSwitch(hass, entry, channel, source_key="line", attr_name="Line Source"))
        entities.append(Fa860SourceSwitch(hass, entry, channel, source_key="ble", attr_name="BLE Source"))
        entities.append(Fa860SourceSwitch(hass, entry, channel, source_key="digital", attr_name="Digital Source"))
    async_add_entities(entities)


class Fa860ChannelRestoreEntity(RestoreEntity):
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, channel: int) -> None:
        self.hass = hass
        self._entry = entry
        self._channel = channel

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_channel_{self._channel}")},
            manufacturer="HiVi",
            model="FA860",
            name=f"CH{self._channel}",
        )

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        return {"channel": self._channel}

    @property
    def available(self) -> bool:
        return is_entry_available(self.hass, self._entry.entry_id)

    @callback
    def _handle_state_updated(self, entry_id: str, channel: int) -> None:
        if entry_id == self._entry.entry_id and channel == self._channel:
            self.async_write_ha_state()

    @callback
    def _handle_availability_updated(self, entry_id: str) -> None:
        if entry_id == self._entry.entry_id:
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._apply_restored_state(last_state.state)
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_STATE_UPDATED, self._handle_state_updated))
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_AVAILABILITY_UPDATED, self._handle_availability_updated))

    def _apply_restored_state(self, state: str) -> None:
        raise NotImplementedError


class Fa860MuteSwitch(Fa860ChannelRestoreEntity, SwitchEntity):
    _attr_name = "Mute"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_channel_{self._channel}_mute"

    @property
    def is_on(self) -> bool:
        return get_channel_state(self.hass, self._entry.entry_id, self._channel).mute

    @property
    def icon(self) -> str:
        return "mdi:volume-off" if self.is_on else "mdi:volume-high"

    async def async_turn_on(self, **kwargs) -> None:
        await async_send_channel_mute_command(self.hass, self._entry.entry_id, self._channel, True)

    async def async_turn_off(self, **kwargs) -> None:
        await async_send_channel_mute_command(self.hass, self._entry.entry_id, self._channel, False)

    def _apply_restored_state(self, state: str) -> None:
        get_channel_state(self.hass, self._entry.entry_id, self._channel).mute = state == "on"


class Fa860SourceSwitch(Fa860ChannelRestoreEntity, SwitchEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, channel: int, *, source_key: str, attr_name: str) -> None:
        super().__init__(hass, entry, channel)
        self._source_key = source_key
        self._attr_name = attr_name

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_channel_{self._channel}_source_{self._source_key}"

    @property
    def is_on(self) -> bool:
        state = get_channel_state(self.hass, self._entry.entry_id, self._channel)
        return {
            "line": state.source_line,
            "ble": state.source_ble,
            "digital": state.source_digital,
        }[self._source_key]

    @property
    def icon(self) -> str:
        if self._source_key == "line":
            return "mdi:audio-input-rca"
        if self._source_key == "ble":
            return "mdi:bluetooth-audio"
        return "mdi:music-note-outline"

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set_value(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set_value(False)

    async def _async_set_value(self, enabled: bool) -> None:
        state = get_channel_state(self.hass, self._entry.entry_id, self._channel)
        params = {
            "channel": self._channel,
            "line": state.source_line,
            "ble": state.source_ble,
            "digital": state.source_digital,
        }
        params[self._source_key] = enabled
        await async_execute_entry_command(self.hass, self._entry.entry_id, SERVICE_SOURCE, params)
        publish_state_update(self.hass, self._entry.entry_id, SERVICE_SOURCE, params)

    def _apply_restored_state(self, state: str) -> None:
        channel_state = get_channel_state(self.hass, self._entry.entry_id, self._channel)
        enabled = state == "on"
        if self._source_key == "line":
            channel_state.source_line = enabled
        elif self._source_key == "ble":
            channel_state.source_ble = enabled
        else:
            channel_state.source_digital = enabled