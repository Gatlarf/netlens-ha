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
        "uptime_24h": "99.5", "devices_unknown": "2", "plugin_updates": "2", "wifi_clients": "3", "wifi_weak": "1", "services_down": "1", "last_scan_duration": "35", "last_scan_hosts": "31", "problems": "0", "version": "0.2.40",
        "devices_flapping": "1",
    }
    for key, value in expected.items():
        assert state(hass, entry, "sensor", key).state == value, key
    assert state(hass, entry, "sensor", "last_scan").state == "2026-10-08T11:58:00+00:00"
    assert state(hass, entry, "binary_sensor", "problem").state == "off"
    assert state(hass, entry, "binary_sensor", "scan_running").state == "off"
    assert state(hass, entry, "sensor", "last_backup").state == "2026-10-08T03:00:00+00:00"
    assert state(hass, entry, "binary_sensor", "backup_problem").state == "off"


async def test_less_useful_sensors_start_disabled(hass, mock_netlens):
    entry = make_entry()
    await setup(hass, entry)
    registry = er.async_get(hass)
    for key in ("devices_stale", "uptime_7d", "last_scan_age", "devices_unknown_type", "devices_private_address", "dhcp_servers"):
        reg = registry.async_get(registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}"))
        assert reg.disabled_by is er.RegistryEntryDisabler.INTEGRATION, key
    reg = registry.async_get(registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_passive_listening"))
    assert reg.disabled_by is er.RegistryEntryDisabler.INTEGRATION


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


async def test_an_older_netlens_without_the_newer_fields_still_works(hass, mock_netlens, summary):
    for key in ("wifi", "services"):
        summary.pop(key)
    summary["devices"].pop("unknown")
    entry = make_entry()
    await setup(hass, entry)
    assert state(hass, entry, "sensor", "devices_total").state == "5"
    for key in ("devices_unknown", "wifi_clients", "wifi_weak", "services_down"):
        assert state(hass, entry, "sensor", key).state == "unknown"  # no value, but no crash


async def test_update_entity_announces_a_newer_netlens(hass, mock_netlens, summary, freezer):
    entry = make_entry()
    await setup(hass, entry)
    up = state(hass, entry, "update", "update")
    assert up.state == "on" and up.attributes["installed_version"] == "0.2.44" and up.attributes["latest_version"] == "0.2.46"
    assert up.attributes["release_url"].endswith("CHANGELOG.md") and up.attributes["plugin_updates_available"] == 2
    summary["update"] = {"current": "0.2.46", "latest": "0.2.46", "available": False, "plugin_updates": 0}
    await poll(hass, freezer)
    assert state(hass, entry, "update", "update").state == "off"


async def test_update_entity_with_an_older_netlens(hass, mock_netlens, summary):
    summary.pop("update")
    entry = make_entry()
    await setup(hass, entry)
    up = state(hass, entry, "update", "update")
    assert up.state == "off" and up.attributes["installed_version"] == "0.2.40"  # nothing newer is claimed


async def test_backup_and_flapping_follow_the_next_poll(hass, mock_netlens, summary, freezer):
    entry = make_entry()
    await setup(hass, entry)
    summary["backup"].update(last_ok=False, last_error="disk full", last_at="2026-10-08T12:30:00Z")
    summary["devices"]["flapping"] = 4
    summary["problems"], summary["problem"] = 1, True
    await poll(hass, freezer)
    backup = state(hass, entry, "binary_sensor", "backup_problem")
    assert backup.state == "on" and backup.attributes["error"] == "disk full"
    assert state(hass, entry, "sensor", "devices_flapping").state == "4"
    assert state(hass, entry, "binary_sensor", "problem").attributes["backup_failed"] is True


async def test_enabled_extra_sensors_show_the_identification_numbers(hass, mock_netlens):
    entry = make_entry()
    registry = er.async_get(hass)
    entry.add_to_hass(hass)
    for key in ("devices_unknown_type", "devices_private_address", "dhcp_servers"):
        registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_{key}", config_entry=entry, disabled_by=None)
    registry.async_get_or_create("binary_sensor", DOMAIN, f"{entry.entry_id}_passive_listening", config_entry=entry, disabled_by=None)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, entry, "sensor", "devices_unknown_type").state == "3"
    assert state(hass, entry, "sensor", "devices_private_address").state == "2"
    assert state(hass, entry, "sensor", "dhcp_servers").state == "1"
    passive = state(hass, entry, "binary_sensor", "passive_listening")
    assert passive.state == "on" and passive.attributes["devices_updated"] == 7


async def test_a_netlens_without_these_fields_gives_unknown_not_errors(hass, mock_netlens, summary):
    for key in ("identification", "backup", "netchecks", "passive"):
        summary.pop(key)
    summary["devices"].pop("flapping")
    entry = make_entry()
    await setup(hass, entry)
    assert state(hass, entry, "sensor", "devices_flapping").state == "unknown"
    assert state(hass, entry, "sensor", "last_backup").state == "unknown"
    assert state(hass, entry, "binary_sensor", "backup_problem").state == "unknown"
    assert state(hass, entry, "binary_sensor", "problem").attributes["backup_failed"] is False


async def test_dns_sensors_when_enabled(hass, mock_netlens):
    entry = make_entry()
    registry = er.async_get(hass)
    entry.add_to_hass(hass)
    for key in ("dns_pending", "dns_conflicts"):
        registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_{key}", config_entry=entry, disabled_by=None)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, entry, "sensor", "dns_pending").state == "2" and state(hass, entry, "sensor", "dns_conflicts").state == "1"


async def test_container_sensors_when_enabled(hass, mock_netlens):
    entry = make_entry()
    registry = er.async_get(hass)
    entry.add_to_hass(hass)
    for key in ("containers_running", "containers_unhealthy", "containers_restarting"):
        registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_{key}", config_entry=entry, disabled_by=None)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert state(hass, entry, "sensor", "containers_running").state == "7"
    assert state(hass, entry, "sensor", "containers_unhealthy").state == "2" and state(hass, entry, "sensor", "containers_restarting").state == "1"
