import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.netlens.const import DOMAIN
from .conftest import URL, make_entry
from .helpers import entity_id, poll, setup, state


async def test_setup_creates_the_hub_sensors(hass, mock_netlens):
    entry = make_entry()
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    expected = {
        "devices_total": "5", "devices_online": "4", "devices_offline": "1", "devices_new_24h": "1", "open_ports": "17", "events_24h": "6",
        "uptime_24h": "99.5", "last_scan_duration": "35", "last_scan_hosts": "31", "problems": "0", "version": "0.2.40",
    }
    for key, value in expected.items():
        assert state(hass, entry, "sensor", key).state == value, key
    assert state(hass, entry, "sensor", "last_scan").state == "2026-10-08T11:58:00+00:00"
    assert state(hass, entry, "binary_sensor", "problem").state == "off"
    assert state(hass, entry, "binary_sensor", "scan_running").state == "off"


async def test_less_useful_sensors_start_disabled(hass, mock_netlens):
    entry = make_entry()
    await setup(hass, entry)
    registry = er.async_get(hass)
    for key in ("devices_stale", "uptime_7d", "last_scan_age"):
        reg = registry.async_get(registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}"))
        assert reg.disabled_by is er.RegistryEntryDisabler.INTEGRATION, key


async def test_hub_device_and_one_request_per_poll(hass, mock_netlens, freezer):
    entry = make_entry()
    await setup(hass, entry)
    hub = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert hub.name == "Netlens" and hub.sw_version == "0.2.40" and hub.configuration_url == URL
    calls = len([c for c in mock_netlens.mock_calls if "stats/summary" in str(c[1])])
    assert calls == 1  # one request feeds every entity
    await poll(hass, freezer)
    assert len([c for c in mock_netlens.mock_calls if "stats/summary" in str(c[1])]) == 2


async def test_values_follow_the_next_poll(hass, mock_netlens, summary, freezer):
    entry = make_entry()
    await setup(hass, entry)
    summary["devices"]["online"] = 2
    summary["scans"]["running"] = True
    summary["problems"], summary["problem"] = 2, True
    summary["scans"]["failed_24h"] = 1
    summary["plugins"][0].update(ok=False, error="login refused")
    await poll(hass, freezer)
    assert state(hass, entry, "sensor", "devices_online").state == "2"
    assert state(hass, entry, "binary_sensor", "scan_running").state == "on"
    problem = state(hass, entry, "binary_sensor", "problem")
    assert problem.state == "on" and problem.attributes["failing_plugins"] == {"asus": "login refused"} and problem.attributes["scans_failed_24h"] == 1


async def test_netlens_going_away_makes_entities_unavailable_then_recovers(hass, aioclient_mock, summary, freezer):
    aioclient_mock.get(f"{URL}/api/stats/summary", json=summary)
    entry = make_entry()
    await setup(hass, entry)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", exc=aiohttp.ClientError("down"))
    await poll(hass, freezer)
    assert state(hass, entry, "sensor", "devices_total").state == "unavailable"
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", json=summary)
    await poll(hass, freezer)
    assert state(hass, entry, "sensor", "devices_total").state == "5"


async def test_setup_retries_when_netlens_is_down(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/api/stats/summary", status=500)
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_a_refused_token_starts_reauthentication(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/api/stats/summary", status=401)
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert [f for f in hass.config_entries.flow.async_progress() if f["context"]["source"] == "reauth"]


async def test_old_netlens_without_the_statistics_api(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/api/stats/summary", status=404)
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_and_remove(hass, mock_netlens):
    entry = make_entry()
    await setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert state(hass, entry, "sensor", "devices_total").state == "unavailable"
