"""Diagnostics download (the token is redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import NetlensConfigEntry
from .const import CONF_TOKEN

TO_REDACT = {CONF_TOKEN, "mac", "ip", "name", "parent_name", "last_seen"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: NetlensConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = dict(coordinator.data or {})
    devices = data.pop("device_list", [])
    return {
        "entry": async_redact_data({**entry.data, "options": dict(entry.options)}, TO_REDACT),
        "summary": data,
        "devices": async_redact_data(devices, TO_REDACT),
        "last_update_success": coordinator.last_update_success,
    }
