"""An update entity: tells you when a newer Netlens has been published (it cannot install it for you)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NetlensConfigEntry
from .entity import NetlensHubEntity

CHANGELOG = "https://github.com/Gatlarf/netlens/blob/main/CHANGELOG.md"


async def async_setup_entry(hass: HomeAssistant, entry: NetlensConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([NetlensUpdate(entry.runtime_data, entry)])


class NetlensUpdate(NetlensHubEntity, UpdateEntity):
    _attr_translation_key = "netlens_update"
    _attr_title = "Netlens"
    _attr_release_url = CHANGELOG

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "update")

    @property
    def _update(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("update") or {}

    @property
    def installed_version(self) -> str | None:
        return self._update.get("current") or (self.coordinator.data or {}).get("version")

    @property
    def latest_version(self) -> str | None:
        # an older Netlens does not report this: then there is nothing newer to announce
        return self._update.get("latest") or self.installed_version

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"plugin_updates_available": self._update.get("plugin_updates")}
