"""Sensors for the always-on (core) devices (Netlens 0.3.162 and later)."""

from homeassistant.helpers import entity_registry as er

from .conftest import make_entry
from .helpers import entity_id, setup


async def test_core_sensors_show_the_always_on_devices(hass, mock_netlens, summary):
    summary["core"] = {"devices": 6, "online": 5, "uptime": {"24h": 99.4, "7d": 99.1, "30d": 98.9}, "flapping": 0}
    entry = make_entry()
    await setup(hass, entry)
    assert float(hass.states.get(entity_id(hass, entry, "sensor", "core_uptime_24h")).state) == 99.4
    assert hass.states.get(entity_id(hass, entry, "sensor", "core_devices_online")).state == "5"
    assert er.async_get(hass).async_get(entity_id(hass, entry, "sensor", "core_uptime_7d")).disabled_by is not None


async def test_without_marked_devices_the_core_sensors_start_disabled(hass, mock_netlens, summary):
    summary["core"] = {"devices": 0, "online": 0, "uptime": {"24h": None, "7d": None, "30d": None}, "flapping": 0}
    entry = make_entry()
    await setup(hass, entry)
    registry = er.async_get(hass)
    for key in ("core_uptime_24h", "core_devices_online"):
        assert registry.async_get(entity_id(hass, entry, "sensor", key)).disabled_by is not None
