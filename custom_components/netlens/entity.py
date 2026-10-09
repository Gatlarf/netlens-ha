"""Shared entity bases and device registry helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICES, DOMAIN
from .coordinator import NetlensCoordinator, device_key


def hub_info(entry: ConfigEntry, data: dict[str, Any] | None) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Netlens",
        manufacturer="Netlens",
        model="Network scanner",
        sw_version=(data or {}).get("version"),
        configuration_url=entry.data.get("url"),
    )


def tracked_keys(entry: ConfigEntry) -> list[str]:
    return list(entry.options.get(CONF_DEVICES, []))


def _depth(devices_by_id: dict[int, dict[str, Any]], device: dict[str, Any]) -> int:
    depth, seen = 0, set()
    while device.get("parent_id") in devices_by_id and device["id"] not in seen:
        seen.add(device["id"])
        device = devices_by_id[device["parent_id"]]
        depth += 1
    return depth


def device_info_for(entry: ConfigEntry, coordinator: NetlensCoordinator, key: str) -> DeviceInfo | None:
    """Device registry entry of a tracked Netlens device; it hangs below its parent when the parent is tracked too."""
    device = coordinator.devices.get(key)
    if device is None:
        return None
    by_id = {d["id"]: d for d in coordinator.data["device_list"]}
    tracked = set(tracked_keys(entry))
    parent = by_id.get(device.get("parent_id"))
    via = (DOMAIN, entry.entry_id)
    if parent is not None and device_key(parent) in tracked:
        via = (DOMAIN, f"{entry.entry_id}_{device_key(parent)}")
    info = DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{key}")},
        name=device["name"],
        manufacturer=device.get("vendor"),
        model=device.get("type"),
        via_device=via,
        configuration_url=f"{coordinator.api.url}/#/device/{device['id']}",
    )
    if device.get("group"):  # the Netlens group (room, floor...) becomes the suggested area; the user can still change it
        info["suggested_area"] = device["group"]
    if device.get("mac"):
        info["connections"] = {(CONNECTION_NETWORK_MAC, device["mac"])}
    return info


def register_devices(hass, entry: ConfigEntry, coordinator: NetlensCoordinator) -> None:
    """Create or update the hub and the tracked devices, parents first, so `via_device` always exists."""
    registry = dr.async_get(hass)
    hub = hub_info(entry, coordinator.data)
    registry.async_get_or_create(config_entry_id=entry.entry_id, **hub)
    by_id = {d["id"]: d for d in coordinator.data["device_list"]}
    keyed = sorted(
        ((k, d) for k, d in coordinator.devices.items() if k in tracked_keys(entry)),
        key=lambda kd: _depth(by_id, kd[1]),
    )
    for key, _device in keyed:
        info = device_info_for(entry, coordinator, key)
        if info is not None:
            registry.async_get_or_create(config_entry_id=entry.entry_id, **info)


class NetlensHubEntity(CoordinatorEntity[NetlensCoordinator]):
    """Entity that belongs to the Netlens hub device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NetlensCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = hub_info(entry, coordinator.data)


class NetlensDeviceEntity(CoordinatorEntity[NetlensCoordinator]):
    """Entity that belongs to one tracked Netlens device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NetlensCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._device_key = key
        self._attr_unique_id = f"{entry.entry_id}_dev_{key}"
        self._attr_device_info = device_info_for(entry, coordinator, key)

    @property
    def netlens_device(self) -> dict[str, Any] | None:
        return self.coordinator.devices.get(self._device_key)

    @property
    def available(self) -> bool:
        return super().available and self.netlens_device is not None
