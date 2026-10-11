"""Reverse proxy sites and certificates, containers with a newer image, the new event kinds and the maintenance skip."""

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.netlens.const import CONF_SKIP_MAINTENANCE, DOMAIN
from .conftest import URL, make_entry
from .helpers import entity_id, poll, setup

SITES = {"total": 7, "enabled": 6, "unmatched": 1, "expiring": 3, "down": 1, "certificates": 3, "certificates_expiring": 1, "certificates_expired": 0, "next_expiry_days": 9}


async def test_site_and_certificate_sensors_appear_enabled_when_netlens_has_sites(hass, mock_netlens, summary):
    summary["sites"] = SITES
    summary["guests"]["image_updates"] = 4
    entry = make_entry()
    await setup(hass, entry)
    assert hass.states.get(entity_id(hass, entry, "sensor", "sites_down")).state == "1"
    assert hass.states.get(entity_id(hass, entry, "sensor", "certificates_expiring")).state == "1"
    assert hass.states.get(entity_id(hass, entry, "sensor", "certificate_days_left")).state == "9"
    problem = hass.states.get(entity_id(hass, entry, "binary_sensor", "certificate_problem"))
    assert problem.state == "on" and problem.attributes["next_expiry_days"] == 9 and problem.attributes["certificates"] == 3
    # the less useful ones exist but start disabled
    registry = er.async_get(hass)
    for key in ("sites_total", "sites_unmatched", "containers_image_updates"):
        assert registry.async_get(entity_id(hass, entry, "sensor", key)).disabled_by is not None


async def test_without_sites_the_sensors_start_disabled_and_the_problem_is_unknown(hass, mock_netlens):
    entry = make_entry()           # the standard summary has no sites (an older Netlens)
    await setup(hass, entry)
    registry = er.async_get(hass)
    for key in ("sites_down", "certificates_expiring", "certificate_days_left"):
        assert registry.async_get(entity_id(hass, entry, "sensor", key)).disabled_by is not None
    assert registry.async_get(entity_id(hass, entry, "binary_sensor", "certificate_problem")).disabled_by is not None


async def test_a_good_certificate_is_no_problem(hass, mock_netlens, summary):
    summary["sites"] = {**SITES, "certificates_expiring": 0, "next_expiry_days": 60, "down": 0}
    entry = make_entry()
    await setup(hass, entry)
    assert hass.states.get(entity_id(hass, entry, "binary_sensor", "certificate_problem")).state == "off"
    assert hass.states.get(entity_id(hass, entry, "sensor", "certificate_days_left")).state == "60"


async def test_container_and_certificate_events_reach_home_assistant(hass, mock_netlens, summary, freezer):
    names = ("certificate_expiring", "update_available", "container_unhealthy", "container_restarting", "container_stopped", "guest_stopped", "guest_started", "login_failed")
    seen = {n: async_capture_events(hass, f"netlens_{n}") for n in names}
    entry = make_entry()
    await setup(hass, entry)
    kinds = ["cert_expiring", "guest_update_available", "container_unhealthy", "container_restarting", "container_stopped", "guest_stopped", "guest_started", "login_failed"]
    summary["events"]["last_id"] = 40 + len(kinds)
    mock_netlens.get(f"{URL}/api/events", json=[{"id": 41 + i, "ts": "2026-10-08T12:00:00Z", "device_id": None, "kind": k, "detail": f"detail {k}"} for i, k in enumerate(kinds)])
    await poll(hass, freezer)
    for name, kind in zip(names, kinds):
        assert [e.data["detail"] for e in seen[name]] == [f"detail {kind}"], name


async def test_events_held_back_by_a_maintenance_window_are_skipped_unless_asked_for(hass, mock_netlens, summary, freezer):
    offline = async_capture_events(hass, "netlens_device_offline")
    entry = make_entry()
    await setup(hass, entry)
    summary["events"]["last_id"] = 43
    mock_netlens.get(f"{URL}/api/events", json=[
        {"id": 41, "ts": "2026-10-08T12:00:00Z", "device_id": 3, "kind": "device_offline", "detail": "a", "maintenance": "AiMesh update"},
        {"id": 42, "ts": "2026-10-08T12:00:10Z", "device_id": 3, "kind": "device_offline", "detail": "b", "maintenance": None},
        {"id": 43, "ts": "2026-10-08T12:00:20Z", "device_id": 3, "kind": "device_offline", "detail": "c"},
    ])
    await poll(hass, freezer)
    assert [e.data["detail"] for e in offline] == ["b", "c"] and offline[0].data["maintenance"] is None


async def test_the_maintenance_skip_can_be_switched_off(hass, mock_netlens, summary, freezer):
    offline = async_capture_events(hass, "netlens_device_offline")
    entry = make_entry(options={CONF_SKIP_MAINTENANCE: False})
    await setup(hass, entry)
    summary["events"]["last_id"] = 41
    mock_netlens.get(f"{URL}/api/events", json=[{"id": 41, "ts": "2026-10-08T12:00:00Z", "device_id": 3, "kind": "device_offline", "detail": "a", "maintenance": "AiMesh update"}])
    await poll(hass, freezer)
    assert len(offline) == 1 and offline[0].data["maintenance"] == "AiMesh update"
