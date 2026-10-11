"""One poll for the whole integration: a single request per interval, however many entities there are."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NetlensApi, NetlensApiVersionError, NetlensAuthError, NetlensConnectionError, NetlensError
from .const import CONF_SCAN_INTERVAL, CONF_SKIP_MAINTENANCE, CONF_TRACK_EVENTS, DEFAULT_SCAN_INTERVAL, DOMAIN, EVENT_MAP

_LOGGER = logging.getLogger(__name__)


def device_key(device: dict[str, Any]) -> str:
    """Stable key of a Netlens device: its MAC address, or its IP address when it has none."""
    mac = device.get("mac")
    return mac.lower() if mac else f"ip-{device.get('ip')}"


class NetlensCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches /api/stats/summary and turns new Netlens events into Home Assistant events."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: NetlensApi) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry, update_interval=timedelta(seconds=interval))
        self.api = api
        self._last_event_id: int | None = None

    @property
    def devices(self) -> dict[str, dict[str, Any]]:
        """Netlens devices by key."""
        return {device_key(d): d for d in (self.data or {}).get("device_list", [])}

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.summary()
        except NetlensAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except NetlensApiVersionError as exc:
            raise UpdateFailed(str(exc)) from exc
        except NetlensConnectionError as exc:
            raise UpdateFailed(str(exc)) from exc
        if self.config_entry.options.get(CONF_TRACK_EVENTS, True):
            await self._fire_new_events(data)
        return data

    async def _fire_new_events(self, data: dict[str, Any]) -> None:
        latest = data.get("events", {}).get("last_id", 0)
        if self._last_event_id is None:
            self._last_event_id = latest  # the first poll only remembers where we are: no flood of old events
            return
        if latest <= self._last_event_id:
            return
        try:
            events = await self.api.events(self._last_event_id)
        except NetlensError as exc:
            _LOGGER.debug("could not read the Netlens events: %s", exc)
            return
        by_id = {d["id"]: d for d in data.get("device_list", [])}
        for event in events:
            self._last_event_id = max(self._last_event_id, event["id"])
            name = EVENT_MAP.get(event.get("kind"))
            if name is None:
                continue
            if event.get("maintenance") and self.config_entry.options.get(CONF_SKIP_MAINTENANCE, True):
                continue  # Netlens held this one back too: a device in a maintenance window going offline is expected
            device = by_id.get(event.get("device_id")) or {}
            self.hass.bus.async_fire(
                name,
                {
                    "entry_id": self.config_entry.entry_id,
                    "event_id": event["id"],
                    "time": event.get("ts"),
                    "detail": event.get("detail"),
                    "maintenance": event.get("maintenance"),
                    "device_id": event.get("device_id"),
                    "device_name": device.get("name"),
                    "ip": device.get("ip"),
                    "mac": device.get("mac"),
                },
            )
