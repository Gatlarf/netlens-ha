"""The Netlens integration: network statistics and device presence from a Netlens scanner."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NetlensApi
from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN
from .coordinator import NetlensCoordinator
from .entity import register_devices, tracked_keys

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type NetlensConfigEntry = ConfigEntry[NetlensCoordinator]


def _remove_untracked(hass: HomeAssistant, entry: NetlensConfigEntry) -> None:
    """Drop the entities and devices of Netlens devices that are no longer tracked."""
    tracked = set(tracked_keys(entry))
    prefix = f"{entry.entry_id}_dev_"
    entities = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entities, entry.entry_id):
        if entity.unique_id.startswith(prefix) and entity.unique_id[len(prefix):] not in tracked:
            entities.async_remove(entity.entity_id)
    devices = dr.async_get(hass)
    device_prefix = f"{entry.entry_id}_"
    for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier.startswith(device_prefix) and identifier[len(device_prefix):] not in tracked:
                devices.async_remove_device(device.id)


async def async_setup_entry(hass: HomeAssistant, entry: NetlensConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    coordinator = NetlensCoordinator(hass, entry, NetlensApi(session, entry.data[CONF_URL], entry.data[CONF_TOKEN]))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _remove_untracked(hass, entry)
    register_devices(hass, entry, coordinator)
    # names, vendors and parents can change in Netlens: keep the device registry in step
    entry.async_on_unload(coordinator.async_add_listener(lambda: register_devices(hass, entry, coordinator)))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def _options_updated(hass: HomeAssistant, entry: NetlensConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NetlensConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
