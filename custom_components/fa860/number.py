from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, MIX_LINE_LABELS, MIX_TAIL_LABELS, SIGNAL_STATE_UPDATED, SERVICE_MIX_LINE, SERVICE_MIX_TAIL, SERVICE_VOLUME, get_channel_state, get_entry_client, publish_state_update


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    entities: list[NumberEntity] = []
    for channel in range(1, 9):
        entities.append(Fa860VolumeNumber(hass, entry, channel))
        for index, label in enumerate(MIX_LINE_LABELS):
            entities.append(Fa860MixLineNumber(hass, entry, channel, index=index, label=label))
        for key, label in MIX_TAIL_LABELS.items():
            entities.append(Fa860MixTailNumber(hass, entry, channel, key=key, label=label))
    async_add_entities(entities)


class Fa860ChannelNumber(RestoreEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

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

    @callback
    def _handle_state_updated(self, entry_id: str, channel: int) -> None:
        if entry_id == self._entry.entry_id and channel == self._channel:
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in {"unknown", "unavailable"}:
            self._apply_restored_value(float(last_state.state))
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_STATE_UPDATED, self._handle_state_updated))

    def _apply_restored_value(self, value: float) -> None:
        raise NotImplementedError


class Fa860VolumeNumber(Fa860ChannelNumber):
    _attr_name = "Volume"
    _attr_native_min_value = -60
    _attr_native_max_value = 0
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "dB"
    _attr_icon = "mdi:volume-high"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_channel_{self._channel}_volume"

    @property
    def native_value(self) -> float:
        return float(get_channel_state(self.hass, self._entry.entry_id, self._channel).volume_db)

    async def async_set_native_value(self, value: float) -> None:
        state = get_channel_state(self.hass, self._entry.entry_id, self._channel)
        params = {
            "channel": self._channel,
            "db": int(round(value)),
            "mute": state.mute,
        }
        client = get_entry_client(self.hass, self._entry.entry_id)
        await client.async_command(SERVICE_VOLUME, params)
        publish_state_update(self.hass, self._entry.entry_id, SERVICE_VOLUME, params)

    def _apply_restored_value(self, value: float) -> None:
        get_channel_state(self.hass, self._entry.entry_id, self._channel).volume_db = int(round(value))


class Fa860MixLineNumber(Fa860ChannelNumber):
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, channel: int, *, index: int, label: str) -> None:
        super().__init__(hass, entry, channel)
        self._index = index
        self._attr_name = label

    @property
    def icon(self) -> str:
        return "mdi:ray-start-arrow"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_channel_{self._channel}_mix_line_{self._index + 1}"

    @property
    def native_value(self) -> float:
        return float(get_channel_state(self.hass, self._entry.entry_id, self._channel).mix_line[self._index])

    async def async_set_native_value(self, value: float) -> None:
        state = get_channel_state(self.hass, self._entry.entry_id, self._channel)
        values = list(state.mix_line)
        values[self._index] = int(round(value))
        params = {
            "channel": self._channel,
            "values": values,
        }
        client = get_entry_client(self.hass, self._entry.entry_id)
        await client.async_command(SERVICE_MIX_LINE, params)
        publish_state_update(self.hass, self._entry.entry_id, SERVICE_MIX_LINE, params)

    def _apply_restored_value(self, value: float) -> None:
        get_channel_state(self.hass, self._entry.entry_id, self._channel).mix_line[self._index] = int(round(value))


class Fa860MixTailNumber(Fa860ChannelNumber):
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, channel: int, *, key: str, label: str) -> None:
        super().__init__(hass, entry, channel)
        self._key = key
        self._attr_name = label

    @property
    def icon(self) -> str:
        if self._key.startswith("digital"):
            return "mdi:music-note-outline"
        return "mdi:bluetooth-audio"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_channel_{self._channel}_mix_tail_{self._key}"

    @property
    def native_value(self) -> float:
        return float(get_channel_state(self.hass, self._entry.entry_id, self._channel).mix_tail[self._key])

    async def async_set_native_value(self, value: float) -> None:
        state = get_channel_state(self.hass, self._entry.entry_id, self._channel)
        values = dict(state.mix_tail)
        values[self._key] = int(round(value))
        params = {
            "channel": self._channel,
            **values,
        }
        client = get_entry_client(self.hass, self._entry.entry_id)
        await client.async_command(SERVICE_MIX_TAIL, params)
        publish_state_update(self.hass, self._entry.entry_id, SERVICE_MIX_TAIL, params)

    def _apply_restored_value(self, value: float) -> None:
        get_channel_state(self.hass, self._entry.entry_id, self._channel).mix_tail[self._key] = int(round(value))