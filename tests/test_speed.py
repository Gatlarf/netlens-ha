"""Internet speed sensors (Netlens 0.3.154 and later)."""

from homeassistant.helpers import entity_registry as er

from .conftest import make_entry
from .helpers import entity_id, setup

SPEED = {"total": 12, "internet": {"ts": "2026-10-12T06:00:00Z", "age_s": 21600, "down_mbps": 487.3, "up_mbps": 47.9, "latency_ms": 11.2, "jitter_ms": 1.4, "server": "Brussels", "isp": "ISP", "target": "Cloudflare"},
         "last_ok": True, "failed_24h": 0, "avg_down_7d": 480.0, "avg_up_7d": 48.0, "tests_7d": 28, "iperf": None}


async def test_speed_sensors_show_the_latest_internet_test(hass, mock_netlens, summary):
    summary["speed"] = SPEED
    entry = make_entry()
    await setup(hass, entry)
    assert float(hass.states.get(entity_id(hass, entry, "sensor", "speed_download")).state) == 487.3
    assert hass.states.get(entity_id(hass, entry, "sensor", "speed_download")).attributes["unit_of_measurement"] == "Mbit/s"
    assert float(hass.states.get(entity_id(hass, entry, "sensor", "speed_upload")).state) == 47.9
    assert float(hass.states.get(entity_id(hass, entry, "sensor", "speed_ping")).state) == 11.2
    registry = er.async_get(hass)
    for key in ("speed_jitter", "speed_last_test"):
        assert registry.async_get(entity_id(hass, entry, "sensor", key)).disabled_by is not None       # the less useful ones start disabled


async def test_without_speed_tests_the_sensors_start_disabled(hass, mock_netlens):
    entry = make_entry()                      # the standard summary has no speed block (an older Netlens)
    await setup(hass, entry)
    registry = er.async_get(hass)
    for key in ("speed_download", "speed_upload", "speed_ping"):
        assert registry.async_get(entity_id(hass, entry, "sensor", key)).disabled_by is not None
