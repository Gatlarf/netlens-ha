from homeassistant.components.diagnostics import REDACTED
from pytest_homeassistant_custom_component.common import async_capture_events
from custom_components.netlens.diagnostics import async_get_config_entry_diagnostics

from custom_components.netlens.const import CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_TRACK_EVENTS
from .conftest import URL, make_entry
from .helpers import poll, setup

EVENTS = [
    {"id": 41, "ts": "2026-10-08T12:00:30Z", "device_id": 3, "kind": "device_offline", "detail": "192.168.0.50"},
    {"id": 42, "ts": "2026-10-08T12:00:40Z", "device_id": 4, "kind": "device_new", "detail": "192.168.0.60 Acme"},
    {"id": 43, "ts": "2026-10-08T12:00:50Z", "device_id": 5, "kind": "os_changed", "detail": "a -> b"},  # no Home Assistant event for this kind
    {"id": 44, "ts": "2026-10-08T12:01:00Z", "device_id": 5, "kind": "port_opened", "detail": "445"},
    {"id": 45, "ts": "2026-10-08T12:01:10Z", "device_id": None, "kind": "service_down", "detail": "Web (192.168.0.70:80) is down: refused"},
    {"id": 46, "ts": "2026-10-08T12:01:20Z", "device_id": 3, "kind": "wifi_roamed", "detail": "Garden -> Attic (5 GHz)"},
    {"id": 47, "ts": "2026-10-08T12:01:30Z", "device_id": 5, "kind": "port_unexpected", "detail": "tcp/23 telnet"},
    {"id": 48, "ts": "2026-10-08T12:01:40Z", "device_id": 5, "kind": "port_missing", "detail": "tcp/443 https"},
    {"id": 49, "ts": "2026-10-08T12:01:50Z", "device_id": 5, "kind": "port_closed", "detail": "tcp/8080"},
    {"id": 50, "ts": "2026-10-08T12:02:00Z", "device_id": None, "kind": "backup_failed", "detail": "disk full"},
    {"id": 51, "ts": "2026-10-08T12:02:10Z", "device_id": None, "kind": "dhcp_rogue", "detail": "A new DHCP server answered: 192.168.0.99"},
    {"id": 52, "ts": "2026-10-08T12:02:20Z", "device_id": 1, "kind": "gateway_changed", "detail": "The MAC address behind the gateway changed"},
]


async def test_new_netlens_events_become_home_assistant_events(hass, mock_netlens, summary, freezer):
    new_device = async_capture_events(hass, "netlens_new_device")
    offline = async_capture_events(hass, "netlens_device_offline")
    port = async_capture_events(hass, "netlens_port_opened")
    svc_down = async_capture_events(hass, "netlens_service_down")
    roamed = async_capture_events(hass, "netlens_wifi_roamed")
    entry = make_entry()
    await setup(hass, entry)
    assert not (new_device or offline or port or svc_down or roamed)  # the first poll only remembers where it is

    extra = {k: async_capture_events(hass, f"netlens_{k}") for k in ("port_unexpected", "port_missing", "port_closed", "backup_failed", "dhcp_rogue", "gateway_changed")}
    summary["events"]["last_id"] = 52
    mock_netlens.get(f"{URL}/api/events", json=EVENTS)
    await poll(hass, freezer)
    assert [e.data["detail"] for e in extra["port_unexpected"]] == ["tcp/23 telnet"] and [e.data["detail"] for e in extra["port_missing"]] == ["tcp/443 https"]
    assert len(extra["port_closed"]) == 1 and extra["backup_failed"][0].data["detail"] == "disk full" and extra["backup_failed"][0].data["device_name"] is None
    assert "192.168.0.99" in extra["dhcp_rogue"][0].data["detail"] and extra["gateway_changed"][0].data["device_name"] == "Router"
    assert [e.data["event_id"] for e in offline] == [41] and offline[0].data["device_name"] == "Laptop" and offline[0].data["mac"] == "aa:00:00:00:00:03"
    assert new_device[0].data["detail"] == "192.168.0.60 Acme" and new_device[0].data["ip"] == "192.168.0.60"
    assert port[0].data["entry_id"] == entry.entry_id and port[0].data["time"] == "2026-10-08T12:01:00Z"
    assert [e.data["detail"] for e in svc_down] == ["Web (192.168.0.70:80) is down: refused"] and svc_down[0].data["device_name"] is None
    assert roamed[0].data["device_name"] == "Laptop" and roamed[0].data["detail"] == "Garden -> Attic (5 GHz)"
    assert "since_id=40" in str([c[1] for c in mock_netlens.mock_calls if "api/events" in str(c[1])][0])

    # nothing new: no more requests and no repeats
    calls = len(mock_netlens.mock_calls)
    await poll(hass, freezer)
    assert len(offline) == 1 and len([c for c in mock_netlens.mock_calls[calls:] if "api/events" in str(c[1])]) == 0


async def test_events_can_be_switched_off(hass, mock_netlens, summary, freezer):
    offline = async_capture_events(hass, "netlens_device_offline")
    entry = make_entry(options={CONF_TRACK_EVENTS: False})
    await setup(hass, entry)
    summary["events"]["last_id"] = 44
    mock_netlens.get(f"{URL}/api/events", json=EVENTS)
    await poll(hass, freezer)
    assert not offline and not [c for c in mock_netlens.mock_calls if "api/events" in str(c[1])]


async def test_a_failing_events_request_does_not_break_the_update(hass, mock_netlens, summary, freezer):
    entry = make_entry()
    await setup(hass, entry)
    summary["events"]["last_id"] = 44
    summary["devices"]["total"] = 9
    mock_netlens.get(f"{URL}/api/events", status=500)
    await poll(hass, freezer)
    from .helpers import state
    assert state(hass, entry, "sensor", "devices_total").state == "9"


async def test_the_poll_interval_is_an_option(hass, mock_netlens, freezer):
    entry = make_entry(options={CONF_SCAN_INTERVAL: 300})
    await setup(hass, entry)
    assert entry.runtime_data.update_interval.total_seconds() == 300


async def test_diagnostics_hide_the_token_and_device_identity(hass, mock_netlens):
    entry = make_entry()
    await setup(hass, entry)
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["entry"][CONF_TOKEN] == REDACTED
    assert "s3cret" not in str(data)
    assert data["summary"]["devices"]["total"] == 5 and "device_list" not in data["summary"]
    assert data["devices"][0]["mac"] == REDACTED and data["devices"][0]["name"] == REDACTED and data["devices"][0]["online"] is True
