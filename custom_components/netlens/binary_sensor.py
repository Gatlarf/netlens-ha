"""Binary sensors: Netlens health, a running scan, and (opt-in) one presence sensor per tracked device."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NetlensConfigEntry
from .entity import NetlensDeviceEntity, NetlensHubEntity, tracked_keys


async def async_setup_entry(hass: HomeAssistant, entry: NetlensConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities([NetlensProblemSensor(coordinator, entry), NetlensScanRunningSensor(coordinator, entry), NetlensBackupProblemSensor(coordinator, entry), NetlensPassiveSensor(coordinator, entry), NetlensCertificateSensor(coordinator, entry)])

    added: set[str] = set()

    @callback
    def add_tracked_devices() -> None:
        """Add a presence sensor for every tracked device that exists in Netlens (also for ones that show up later)."""
        new = [key for key in tracked_keys(entry) if key in coordinator.devices and key not in added]
        if new:
            added.update(new)
            async_add_entities(NetlensPresenceSensor(coordinator, entry, key) for key in new)

    add_tracked_devices()
    entry.async_on_unload(coordinator.async_add_listener(add_tracked_devices))


class NetlensProblemSensor(NetlensHubEntity, BinarySensorEntity):
    """On when a scan failed recently, the last good scan is old, or an enabled plugin is failing."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "problem"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "problem")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["problem"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "problems": data["problems"],
            "scans_failed_24h": data["scans"]["failed_24h"],
            "seconds_since_last_good_scan": data["scans"]["last_ok_age_s"],
            "failing_plugins": {p["id"]: p["error"] for p in data["plugins"] if p["enabled"] and p["ok"] is False},
            "backup_failed": (data.get("backup") or {}).get("last_ok") is False,
        }


class NetlensScanRunningSensor(NetlensHubEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "scan_running"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "scan_running")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["scans"]["running"])


class NetlensBackupProblemSensor(NetlensHubEntity, BinarySensorEntity):
    """On when the last scheduled backup failed; unknown while no backup has run (or scheduled backups are off)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "backup_problem"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "backup_problem")

    @property
    def is_on(self) -> bool | None:
        last_ok = (self.coordinator.data.get("backup") or {}).get("last_ok")
        return None if last_ok is None else not last_ok

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        backup = self.coordinator.data.get("backup") or {}
        return {"enabled": backup.get("enabled"), "last_at": backup.get("last_at"), "error": backup.get("last_error")}


class NetlensCertificateSensor(NetlensHubEntity, BinarySensorEntity):
    """On when a certificate used by a reverse proxy site ends within 14 days or has ended. Unknown without reverse proxy sites."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "certificate_problem"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "certificate_problem")

    @property
    def entity_registry_enabled_default(self) -> bool:
        return bool((self.coordinator.data.get("sites") or {}).get("certificates"))

    @property
    def is_on(self) -> bool | None:
        sites = self.coordinator.data.get("sites") or {}
        if not sites.get("certificates"):
            return None
        return bool(sites.get("certificates_expiring") or sites.get("certificates_expired"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sites = self.coordinator.data.get("sites") or {}
        return {k: sites.get(k) for k in ("certificates", "certificates_expiring", "certificates_expired", "next_expiry_days", "total", "down", "unmatched")}


class NetlensPassiveSensor(NetlensHubEntity, BinarySensorEntity):
    """Is Netlens listening to the announcements devices make (DHCP, mDNS, UPnP)?"""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "passive_listening"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "passive_listening")

    @property
    def is_on(self) -> bool | None:
        passive = self.coordinator.data.get("passive")
        return None if passive is None else bool(passive.get("running"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        passive = self.coordinator.data.get("passive") or {}
        return {"announcements_heard": passive.get("frames"), "devices_updated": passive.get("applied")}


class NetlensPresenceSensor(NetlensDeviceEntity, BinarySensorEntity):
    """Is this device on the network right now (as Netlens sees it)?"""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = None  # the entity takes the device's name

    @property
    def is_on(self) -> bool | None:
        device = self.netlens_device
        return None if device is None else bool(device["online"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = self.netlens_device or {}
        return {k: device.get(k) for k in ("ip", "mac", "vendor", "type", "parent_name", "last_seen", "trusted")}
