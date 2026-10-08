"""Config flow (URL and token), re-authentication and options (poll interval, events, tracked devices)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NetlensApi, NetlensApiVersionError, NetlensAuthError, NetlensConnectionError, normalize_url
from .const import (
    CONF_DEVICES,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_TRACK_EVENTS,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import device_key


class NetlensConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _check(self, url: str, token: str, verify_ssl: bool) -> tuple[dict[str, str], dict[str, Any] | None]:
        errors: dict[str, str] = {}
        summary = None
        try:
            api = NetlensApi(async_get_clientsession(self.hass, verify_ssl=verify_ssl), url, token)
            summary = await api.summary()
        except ValueError:
            errors["base"] = "invalid_url"
        except NetlensAuthError:
            errors["base"] = "invalid_auth"
        except NetlensApiVersionError:
            errors["base"] = "unsupported"
        except NetlensConnectionError:
            errors["base"] = "cannot_connect"
        return errors, summary

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                url = normalize_url(user_input[CONF_URL])
            except ValueError:
                url = ""
            if url:
                await self.async_set_unique_id(url.lower())
                self._abort_if_unique_id_configured()
            errors, summary = await self._check(user_input[CONF_URL], user_input[CONF_TOKEN], user_input[CONF_VERIFY_SSL])
            if not errors:
                return self.async_create_entry(
                    title=f"Netlens ({url.split('://', 1)[1]})",
                    data={CONF_URL: url, CONF_TOKEN: user_input[CONF_TOKEN], CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]},
                )
        defaults = user_input or {}
        schema = vol.Schema({
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, "http://")): selector.TextSelector(),
            vol.Required(CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Required(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)): selector.BooleanSelector(),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, _ = await self._check(entry.data[CONF_URL], user_input[CONF_TOKEN], entry.data.get(CONF_VERIFY_SSL, True))
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]})
        schema = vol.Schema({vol.Required(CONF_TOKEN): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))})
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors, description_placeholders={"url": entry.data[CONF_URL]})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NetlensOptionsFlow()


class NetlensOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        entry = self.config_entry
        coordinator = getattr(entry, "runtime_data", None)
        devices = list((coordinator.devices if coordinator else {}).items())
        options = [
            selector.SelectOptionDict(value=key, label=f"{d['name']} ({d.get('ip') or 'no address'})")
            for key, d in sorted(devices, key=lambda kd: kd[1]["name"].lower())
        ]
        # keep devices that are tracked but currently missing from Netlens selectable, so saving does not drop them silently
        known = {o["value"] for o in options}
        options += [selector.SelectOptionDict(value=k, label=f"{k} (not in Netlens right now)") for k in entry.options.get(CONF_DEVICES, []) if k not in known]
        current = entry.options
        schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL, step=1, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_TRACK_EVENTS, default=current.get(CONF_TRACK_EVENTS, True)): selector.BooleanSelector(),
            vol.Optional(CONF_DEVICES, default=current.get(CONF_DEVICES, [])): selector.SelectSelector(
                selector.SelectSelectorConfig(options=options, multiple=True, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
