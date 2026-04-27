from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.exceptions import HomeAssistantError

from . import CONF_USE_SSL, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_TIMEOUT, DOMAIN, Fa860BridgeClient


def _step_user_schema(user_input: dict[str, object] | None = None) -> vol.Schema:
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, DEFAULT_HOST)): str,
            vol.Required(CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)): vol.Coerce(int),
            vol.Required(CONF_TIMEOUT, default=user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)): vol.Coerce(float),
            vol.Required(CONF_USE_SSL, default=user_input.get(CONF_USE_SSL, False)): bool,
        }
    )


def _merged_input(base: dict[str, object] | None = None, updates: dict[str, object] | None = None) -> dict[str, object]:
    return {
        **(base or {}),
        **(updates or {}),
    }


async def _validate_input(hass, data: dict[str, object]) -> None:
    client = Fa860BridgeClient(
        hass=hass,
        host=str(data[CONF_HOST]),
        port=int(data[CONF_PORT]),
        timeout=float(data[CONF_TIMEOUT]),
        use_ssl=bool(data[CONF_USE_SSL]),
    )
    await client.async_check_health()


class Fa860ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, object] | None = None):
        errors: dict[str, str] = {}
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            try:
                await _validate_input(self.hass, user_input)
            except HomeAssistantError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="FA860 Bridge", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_step_user_schema(user_input), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, object] | None = None):
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await _validate_input(self.hass, user_input)
            except HomeAssistantError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_step_user_schema(_merged_input(entry.data, user_input)),
            errors=errors,
        )