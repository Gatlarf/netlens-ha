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
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import NetlensConfigEntry
from .entity import NetlensHubEntity


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
    NetlensSensorDescription(key="plugin_updates", translation_key="plugin_updates", icon="mdi:puzzle-outline", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement="plugins", value_fn=lambda d: _dig(d, "update", "plugin_updates")),
    NetlensSensorDescription(key="uptime_24h", translation_key="uptime_24h", icon="mdi:chart-line", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement=PERCENTAGE, suggested_display_precision=1, value_fn=lambda d: d["uptime"]["24h"]),
    NetlensSensorDescription(key="uptime_7d", translation_key="uptime_7d", icon="mdi:chart-line", state_class=SensorStateClass.MEASUREMENT,
                             native_unit_of_measurement=PERCENTAGE, suggested_display_precision=1, entity_registry_enabled_default=False,
                             value_fn=lambda d: d["uptime"]["7d"]),
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


class NetlensSensor(NetlensHubEntity, SensorEntity):
    entity_description: NetlensSensorDescription

    def __init__(self, coordinator, entry, description: NetlensSensorDescription) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)
