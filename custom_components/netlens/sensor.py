"""Sensors of the Netlens hub: counts, uptime and scan information."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfDataRate, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback

from . import NetlensConfigEntry
from .entity import NetlensDeviceEntity, NetlensHubEntity, tracked_keys


def _dig(data: dict[str, Any], *path: str) -> Any:
    """Value at a path in the summary, or None when this Netlens version does not report it (additive API)."""
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _last(data: dict[str, Any], key: str) -> Any:
    return (data["scans"].get("last") or {}).get(key)


def _timestamp(value: str | None) -> datetime | None:
    return dt_util.parse_datetime(value) if value else None


@dataclass(frozen=True, kw_only=True)
class NetlensSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    needs_data: str | None = None  # enabled from the start only when this block of the summary has something in it (for example "sites")


SENSORS: tuple[NetlensSensorDescription, ...] = (
    NetlensSensorDescription(key="devices_total", translation_key="devices_total", icon="mdi:lan", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", value_fn=lambda d: d["devices"]["total"]),
    NetlensSensorDescription(key="devices_online", translation_key="devices_online", icon="mdi:lan-connect", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", value_fn=lambda d: d["devices"]["online"]),
    NetlensSensorDescription(key="devices_offline", translation_key="devices_offline", icon="mdi:lan-disconnect", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", value_fn=lambda d: d["devices"]["offline"]),
    NetlensSensorDescription(key="devices_new_24h", translation_key="devices_new_24h", icon="mdi:new-box", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", value_fn=lambda d: d["devices"]["new_24h"]),
    NetlensSensorDescription(key="devices_stale", translation_key="devices_stale", icon="mdi:lan-pending", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", entity_registry_enabled_default=False, value_fn=lambda d: d["devices"]["stale_30d"]),
    NetlensSensorDescription(key="devices_unknown", translation_key="devices_unknown", icon="mdi:help-network-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", value_fn=lambda d: _dig(d, "devices", "unknown")),
    NetlensSensorDescription(key="devices_flapping", translation_key="devices_flapping", icon="mdi:sync-alert", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", value_fn=lambda d: _dig(d, "devices", "flapping")),
    NetlensSensorDescription(key="devices_unknown_type", translation_key="devices_unknown_type", icon="mdi:help-circle-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "identification", "unknown_type")),
    NetlensSensorDescription(key="devices_private_address", translation_key="devices_private_address", icon="mdi:incognito", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "identification", "private_mac")),
    NetlensSensorDescription(key="dhcp_servers", translation_key="dhcp_servers", icon="mdi:server-network", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="servers", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "netchecks", "dhcp_servers")),
    NetlensSensorDescription(key="last_backup", translation_key="last_backup", device_class=SensorDeviceClass.TIMESTAMP,
                             value_fn=lambda d: _timestamp(_dig(d, "backup", "last_at"))),
    NetlensSensorDescription(key="dns_pending", translation_key="dns_pending", icon="mdi:dns-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "dns", "pending")),
    NetlensSensorDescription(key="dns_conflicts", translation_key="dns_conflicts", icon="mdi:alert-circle-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "dns", "conflicts")),
    NetlensSensorDescription(key="speed_download", translation_key="speed_download", icon="mdi:download-network", device_class=SensorDeviceClass.DATA_RATE,
                             native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
                             needs_data="speed", value_fn=lambda d: _dig(d, "speed", "internet", "down_mbps")),
    NetlensSensorDescription(key="speed_upload", translation_key="speed_upload", icon="mdi:upload-network", device_class=SensorDeviceClass.DATA_RATE,
                             native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
                             needs_data="speed", value_fn=lambda d: _dig(d, "speed", "internet", "up_mbps")),
    NetlensSensorDescription(key="speed_ping", translation_key="speed_ping", icon="mdi:timer-outline", device_class=SensorDeviceClass.DURATION,
                             native_unit_of_measurement=UnitOfTime.MILLISECONDS, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
                             needs_data="speed", value_fn=lambda d: _dig(d, "speed", "internet", "latency_ms")),
    NetlensSensorDescription(key="speed_jitter", translation_key="speed_jitter", icon="mdi:chart-bell-curve", device_class=SensorDeviceClass.DURATION,
                             native_unit_of_measurement=UnitOfTime.MILLISECONDS, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
                             entity_registry_enabled_default=False, needs_data="speed", value_fn=lambda d: _dig(d, "speed", "internet", "jitter_ms")),
    NetlensSensorDescription(key="speed_last_test", translation_key="speed_last_test", icon="mdi:speedometer", device_class=SensorDeviceClass.TIMESTAMP,
                             entity_registry_enabled_default=False, needs_data="speed", value_fn=lambda d: _timestamp(_dig(d, "speed", "internet", "ts"))),
    NetlensSensorDescription(key="containers_running", translation_key="containers_running", icon="mdi:docker", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="containers", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "containers", "running")),
    NetlensSensorDescription(key="containers_unhealthy", translation_key="containers_unhealthy", icon="mdi:docker", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="containers", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "containers", "unhealthy")),
    NetlensSensorDescription(key="containers_restarting", translation_key="containers_restarting", icon="mdi:restart-alert", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="containers", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "containers", "restarting")),
    NetlensSensorDescription(key="guests_running", translation_key="guests_running", icon="mdi:server", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="guests", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "guests", "running")),
    NetlensSensorDescription(key="guests_update_available", translation_key="guests_update_available", icon="mdi:package-up", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="guests", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "guests", "update_available")),
    NetlensSensorDescription(key="containers_image_updates", translation_key="containers_image_updates", icon="mdi:package-up", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="containers", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "guests", "image_updates")),
    NetlensSensorDescription(key="sites_total", translation_key="sites_total", icon="mdi:web", state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement="sites",
                             entity_registry_enabled_default=False, needs_data="sites", value_fn=lambda d: _dig(d, "sites", "enabled")),
    NetlensSensorDescription(key="sites_down", translation_key="sites_down", icon="mdi:web-off", state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement="sites",
                             needs_data="sites", value_fn=lambda d: _dig(d, "sites", "down")),
    NetlensSensorDescription(key="sites_unmatched", translation_key="sites_unmatched", icon="mdi:help-network-outline", state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement="sites",
                             entity_registry_enabled_default=False, needs_data="sites", value_fn=lambda d: _dig(d, "sites", "unmatched")),
    NetlensSensorDescription(key="certificates_expiring", translation_key="certificates_expiring", icon="mdi:certificate-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="certificates", needs_data="sites", value_fn=lambda d: _dig(d, "sites", "certificates_expiring")),
    NetlensSensorDescription(key="certificate_days_left", translation_key="certificate_days_left", icon="mdi:certificate", device_class=SensorDeviceClass.DURATION,
                             native_unit_of_measurement=UnitOfTime.DAYS, state_class=SensorStateClass.MEASUREMENT, needs_data="sites",
                             value_fn=lambda d: _dig(d, "sites", "next_expiry_days")),
    NetlensSensorDescription(key="wifi_clients", translation_key="wifi_clients", icon="mdi:wifi", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", value_fn=lambda d: _dig(d, "wifi", "clients")),
    NetlensSensorDescription(key="wifi_weak", translation_key="wifi_weak", icon="mdi:wifi-strength-1-alert", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", value_fn=lambda d: _dig(d, "wifi", "weak")),
    NetlensSensorDescription(key="wifi_signal", translation_key="wifi_signal", device_class=SensorDeviceClass.SIGNAL_STRENGTH, state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="dBm", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "wifi", "avg_rssi")),
    NetlensSensorDescription(key="services_down", translation_key="services_down", icon="mdi:server-network-off", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="checks", value_fn=lambda d: _dig(d, "services", "down")),
    NetlensSensorDescription(key="services_total", translation_key="services_total", icon="mdi:server-network", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="checks", entity_registry_enabled_default=False, value_fn=lambda d: _dig(d, "services", "total")),
    NetlensSensorDescription(key="health_monitored", translation_key="health_monitored", icon="mdi:heart-pulse", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", entity_registry_enabled_default=False, needs_data="health", value_fn=lambda d: _dig(d, "health", "monitored")),
    NetlensSensorDescription(key="health_warning", translation_key="health_warning", icon="mdi:heart-pulse", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", needs_data="health", value_fn=lambda d: _dig(d, "health", "warning")),
    NetlensSensorDescription(key="health_critical", translation_key="health_critical", icon="mdi:heart-broken", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", needs_data="health", value_fn=lambda d: _dig(d, "health", "critical")),
    NetlensSensorDescription(key="health_unreadable", translation_key="health_unreadable", icon="mdi:heart-off-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", entity_registry_enabled_default=False, needs_data="health", value_fn=lambda d: _dig(d, "health", "unreadable")),
    NetlensSensorDescription(key="disk_days_to_full", translation_key="disk_days_to_full", icon="mdi:harddisk", device_class=SensorDeviceClass.DURATION,
                             native_unit_of_measurement=UnitOfTime.DAYS, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0, needs_data="health",
                             value_fn=lambda d: _dig(d, "health", "days_to_full")),
    NetlensSensorDescription(key="remote_sites_total", translation_key="remote_sites_total", icon="mdi:source-branch", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="sites", entity_registry_enabled_default=False, needs_data="remote_sites", value_fn=lambda d: _dig(d, "remote_sites", "total")),
    NetlensSensorDescription(key="remote_sites_silent", translation_key="remote_sites_silent", icon="mdi:source-branch-remove", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="sites", needs_data="remote_sites", value_fn=lambda d: _dig(d, "remote_sites", "silent")),
    NetlensSensorDescription(key="remote_sites_problems", translation_key="remote_sites_problems", icon="mdi:alert-circle-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="problems", needs_data="remote_sites", value_fn=lambda d: _dig(d, "remote_sites", "problems")),
    NetlensSensorDescription(key="plugin_updates", translation_key="plugin_updates", icon="mdi:puzzle-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="plugins", value_fn=lambda d: _dig(d, "update", "plugin_updates")),
    NetlensSensorDescription(key="uptime_24h", translation_key="uptime_24h", icon="mdi:chart-line", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement=PERCENTAGE, suggested_display_precision=1, value_fn=lambda d: d["uptime"]["24h"]),
    NetlensSensorDescription(key="uptime_7d", translation_key="uptime_7d", icon="mdi:chart-line", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement=PERCENTAGE, suggested_display_precision=1, entity_registry_enabled_default=False,
                             value_fn=lambda d: d["uptime"]["7d"]),
    NetlensSensorDescription(key="core_uptime_24h", translation_key="core_uptime_24h", icon="mdi:chart-line-variant", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement=PERCENTAGE, suggested_display_precision=1, needs_data="core", value_fn=lambda d: _dig(d, "core", "uptime", "24h")),
    NetlensSensorDescription(key="core_uptime_7d", translation_key="core_uptime_7d", icon="mdi:chart-line-variant", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement=PERCENTAGE, suggested_display_precision=1, entity_registry_enabled_default=False, needs_data="core",
                             value_fn=lambda d: _dig(d, "core", "uptime", "7d")),
    NetlensSensorDescription(key="core_devices_online", translation_key="core_devices_online", icon="mdi:server-network", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", needs_data="core", value_fn=lambda d: _dig(d, "core", "online")),
    NetlensSensorDescription(key="open_ports", translation_key="open_ports", icon="mdi:ethernet", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="ports", value_fn=lambda d: d["ports"]["open"]),
    NetlensSensorDescription(key="events_24h", translation_key="events_24h", icon="mdi:bell-ring-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="events", value_fn=lambda d: d["events"]["24h"]),
    NetlensSensorDescription(key="last_scan", translation_key="last_scan", device_class=SensorDeviceClass.TIMESTAMP,
                             value_fn=lambda d: _timestamp(_last(d, "finished"))),
    NetlensSensorDescription(key="last_scan_duration", translation_key="last_scan_duration", device_class=SensorDeviceClass.DURATION,
                             native_unit_of_measurement=UnitOfTime.SECONDS, state_class=SensorStateClass.MEASUREMENT,
                             value_fn=lambda d: _last(d, "duration_s")),
    NetlensSensorDescription(key="last_scan_hosts", translation_key="last_scan_hosts", icon="mdi:magnify-scan", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="devices", value_fn=lambda d: _last(d, "hosts_found")),
    NetlensSensorDescription(key="last_scan_age", translation_key="last_scan_age", device_class=SensorDeviceClass.DURATION,
                             native_unit_of_measurement=UnitOfTime.SECONDS, entity_category=EntityCategory.DIAGNOSTIC,
                             entity_registry_enabled_default=False, value_fn=lambda d: d["scans"]["last_ok_age_s"]),
    NetlensSensorDescription(key="problems", translation_key="problems", icon="mdi:alert-circle-outline", entity_category=EntityCategory.DIAGNOSTIC,
                             state_class=SensorStateClass.MEASUREMENT, value_fn=lambda d: d["problems"]),
    NetlensSensorDescription(key="version", translation_key="version", icon="mdi:information-outline", entity_category=EntityCategory.DIAGNOSTIC,
                             value_fn=lambda d: d["version"]),
)


async def async_setup_entry(hass: HomeAssistant, entry: NetlensConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(NetlensSensor(coordinator, entry, description) for description in SENSORS)

    added: set[tuple[str, str]] = set()

    @callback
    def add_device_health() -> None:
        """Health readings of the tracked devices that have health monitoring in Netlens (also for ones that get it later)."""
        new = []
        for key in tracked_keys(entry):
            health = (coordinator.devices.get(key) or {}).get("health")
            if not health:
                continue
            for description in DEVICE_SENSORS:
                if (key, description.key) not in added and (description.key == "health" or health.get(description.reading) is not None):
                    added.add((key, description.key))
                    new.append(NetlensDeviceHealthSensor(coordinator, entry, key, description))
        if new:
            async_add_entities(new)

    add_device_health()
    entry.async_on_unload(coordinator.async_add_listener(add_device_health))


class NetlensSensor(NetlensHubEntity, SensorEntity):
    entity_description: NetlensSensorDescription

    def __init__(self, coordinator, entry, description: NetlensSensorDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def entity_registry_enabled_default(self) -> bool:
        needs = self.entity_description.needs_data
        if needs is None:
            return super().entity_registry_enabled_default
        return bool(_dig(self.coordinator.data, needs, "total") or _dig(self.coordinator.data, needs, "devices") or _dig(self.coordinator.data, needs, "monitored")) \
            and self.entity_description.entity_registry_enabled_default

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)


@dataclass(frozen=True, kw_only=True)
class NetlensDeviceSensorDescription(SensorEntityDescription):
    reading: str          # the key in the device's "health" block


DEVICE_SENSORS: tuple[NetlensDeviceSensorDescription, ...] = (
    NetlensDeviceSensorDescription(key="health", translation_key="device_health", reading="level", icon="mdi:heart-pulse", device_class=SensorDeviceClass.ENUM,
                                   options=["ok", "warning", "critical"]),
    NetlensDeviceSensorDescription(key="cpu", translation_key="device_cpu", reading="cpu", icon="mdi:cpu-64-bit", state_class=SensorStateClass.MEASUREMENT,
                                   native_unit_of_measurement=PERCENTAGE, suggested_display_precision=0),
    NetlensDeviceSensorDescription(key="mem", translation_key="device_memory", reading="mem", icon="mdi:memory", state_class=SensorStateClass.MEASUREMENT,
                                   native_unit_of_measurement=PERCENTAGE, suggested_display_precision=0),
    NetlensDeviceSensorDescription(key="disk", translation_key="device_disk", reading="disk", icon="mdi:harddisk", state_class=SensorStateClass.MEASUREMENT,
                                   native_unit_of_measurement=PERCENTAGE, suggested_display_precision=0),
    NetlensDeviceSensorDescription(key="temp", translation_key="device_temperature", reading="temp", device_class=SensorDeviceClass.TEMPERATURE,
                                   state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=UnitOfTemperature.CELSIUS, suggested_display_precision=0),
    NetlensDeviceSensorDescription(key="battery", translation_key="device_battery", reading="battery", device_class=SensorDeviceClass.BATTERY,
                                   state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=PERCENTAGE),
)


class NetlensDeviceHealthSensor(NetlensDeviceEntity, SensorEntity):
    """One health reading of a tracked device (processor, memory, fullest disk, temperature, UPS battery) and its overall level."""

    entity_description: NetlensDeviceSensorDescription

    def __init__(self, coordinator, entry, key: str, description: NetlensDeviceSensorDescription) -> None:
        super().__init__(coordinator, entry, key)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_dev_{key}|{description.key}"      # "|" never appears in a MAC or an IP address

    @property
    def native_value(self) -> Any:
        health = (self.netlens_device or {}).get("health") or {}
        return health.get(self.entity_description.reading)

    @property
    def available(self) -> bool:
        return super().available and bool((self.netlens_device or {}).get("health"))
