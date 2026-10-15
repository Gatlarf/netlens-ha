"""Health monitoring and remote sites (Netlens 0.4 and later): hub sensors and the readings of tracked devices."""

from homeassistant.helpers import entity_registry as er

from custom_components.netlens.const import CONF_DEVICES
from .conftest import make_entry
from .helpers import entity_id, setup

NAS = "aa:00:00:00:00:05"


def add_health(summary):
    summary["health"] = {"monitored": 3, "warning": 1, "critical": 1, "unreadable": 1, "problems": 3, "days_to_full": 12.4}
    summary["remote_sites"] = {"total": 2, "silent": 1, "problems": 2, "devices_down": 3, "services_down": 0}
    nas = next(d for d in summary["device_list"] if d["id"] == 5)
    nas["health"] = {"level": "warning", "readable": True, "cpu": 12.5, "mem": 63.0, "disk": 88.2, "temp": 44.0, "battery": None, "rx": 1e6, "tx": 5e5}


async def test_hub_health_sensors(hass, mock_netlens, summary):
    add_health(summary)
    entry = make_entry()
    await setup(hass, entry)
    assert hass.states.get(entity_id(hass, entry, "sensor", "health_warning")).state == "1"
    assert hass.states.get(entity_id(hass, entry, "sensor", "health_critical")).state == "1"
    assert float(hass.states.get(entity_id(hass, entry, "sensor", "disk_days_to_full")).state) == 12.4
    assert hass.states.get(entity_id(hass, entry, "sensor", "remote_sites_silent")).state == "1"
    assert hass.states.get(entity_id(hass, entry, "sensor", "remote_sites_problems")).state == "2"
    problem = hass.states.get(entity_id(hass, entry, "binary_sensor", "health_problem"))
    assert problem.state == "on" and problem.attributes["critical"] == 1
    assert hass.states.get(entity_id(hass, entry, "binary_sensor", "remote_site_problem")).state == "on"


async def test_a_disk_on_course_to_fill_is_a_problem_even_without_warnings(hass, mock_netlens, summary):
    add_health(summary)
    summary["health"].update({"warning": 0, "critical": 0, "days_to_full": 9.0})
    entry = make_entry()
    await setup(hass, entry)
    assert hass.states.get(entity_id(hass, entry, "binary_sensor", "health_problem")).state == "on"
    summary["health"]["days_to_full"] = 40.0


async def test_without_health_monitoring_nothing_is_reported(hass, mock_netlens):
    entry = make_entry()                      # an older Netlens: no health block
    await setup(hass, entry)
    registry = er.async_get(hass)
    for platform, key in (("sensor", "health_warning"), ("sensor", "remote_sites_silent"), ("binary_sensor", "health_problem")):
        assert registry.async_get(entity_id(hass, entry, platform, key)).disabled_by is not None
    assert hass.states.get(entity_id(hass, entry, "binary_sensor", "health_problem")) is None or \
        hass.states.get(entity_id(hass, entry, "binary_sensor", "health_problem")).state in ("unavailable", "unknown")


async def test_tracked_devices_get_their_readings(hass, mock_netlens, summary):
    add_health(summary)
    entry = make_entry(options={CONF_DEVICES: [NAS]})
    await setup(hass, entry)
    assert hass.states.get(entity_id(hass, entry, "sensor", f"dev_{NAS}|health")).state == "warning"
    assert float(hass.states.get(entity_id(hass, entry, "sensor", f"dev_{NAS}|cpu")).state) == 12.5
    assert float(hass.states.get(entity_id(hass, entry, "sensor", f"dev_{NAS}|disk")).state) == 88.2
    assert float(hass.states.get(entity_id(hass, entry, "sensor", f"dev_{NAS}|temp")).state) == 44.0
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", "netlens", f"{entry.entry_id}_dev_{NAS}|battery") is None    # no UPS reading: no entity


async def test_untracked_devices_get_no_health_entities(hass, mock_netlens, summary):
    add_health(summary)
    entry = make_entry()
    await setup(hass, entry)
    registry = er.async_get(hass)
    assert not [e for e in er.async_entries_for_config_entry(registry, entry.entry_id) if "_dev_" in e.unique_id]


async def test_untracking_removes_the_health_entities_too(hass, mock_netlens, summary):
    add_health(summary)
    entry = make_entry(options={CONF_DEVICES: [NAS]})
    await setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.config_entries.async_update_entry(entry, options={CONF_DEVICES: []})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert not [e for e in er.async_entries_for_config_entry(registry, entry.entry_id) if "_dev_" in e.unique_id]
