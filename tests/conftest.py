"""Fixtures: a fake Netlens summary and helpers to mock its HTTP API."""

import copy

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMockResponse

from custom_components.netlens.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN

URL = "http://netlens.test:8080"
TOKEN = "s3cret-token"

SUMMARY = {
    "api": 1,
    "version": "0.2.40",
    "generated": "2026-10-08T12:00:00Z",
    "devices": {"total": 5, "online": 4, "offline": 1, "new_24h": 1, "new_7d": 2, "stale_30d": 0, "unknown": 2, "flapping": 1},
    "identification": {"unknown_type": 3, "private_mac": 2, "no_vendor": 1, "manual_type": 0, "gentle": 1, "nameless": 2, "no_os": 4},
    "backup": {"enabled": True, "last_at": "2026-10-08T03:00:00Z", "last_ok": True, "last_error": None, "age_s": 32000},
    "netchecks": {"enabled": True, "dhcp_servers": 1, "untrusted": 0, "last_run": "2026-10-08T00:00:00Z", "last_ok": True},
    "dns": {"registered": 12, "pending": 2, "conflicts": 1, "registers_itself": 5, "waiting": 0},
    "passive": {"enabled": True, "running": True, "frames": 40, "applied": 7},
    "wifi": {"clients": 3, "weak": 1, "avg_rssi": -66},
    "services": {"total": 4, "up": 3, "down": 1},
    "uptime": {"24h": 99.5, "7d": 98.25},
    "ports": {"open": 17},
    "events": {"24h": 6, "last_id": 40},
    "scans": {
        "running": False,
        "last": {"kind": "quick", "status": "done", "finished": "2026-10-08T11:58:00Z", "hosts_found": 31, "duration_s": 35},
        "last_ok_age_s": 120,
        "failed_24h": 0,
    },
    "plugins": [{"id": "asus", "enabled": True, "ok": True, "error": None, "ts": "2026-10-08T11:58:30Z"}],
    "update": {"current": "0.2.44", "latest": "0.2.46", "available": True, "plugin_updates": 2},
    "problems": 0,
    "problem": False,
    "device_list": [
        {"id": 1, "name": "Router", "ip": "192.168.0.1", "mac": "aa:00:00:00:00:01", "online": True, "type": "router", "vendor": "ASUS",
         "last_seen": "2026-10-08T11:58:00Z", "trusted": True, "parent_id": None, "parent_name": None},
        {"id": 2, "name": "Mesh node", "ip": "192.168.0.59", "mac": "aa:00:00:00:00:02", "online": True, "type": "ap", "vendor": "ASUS",
         "last_seen": "2026-10-08T11:58:00Z", "parent_id": 1, "parent_name": "Router"},
        {"id": 3, "name": "Laptop", "ip": "192.168.0.50", "mac": "aa:00:00:00:00:03", "online": True, "type": "pc", "vendor": "Dell",
         "last_seen": "2026-10-08T11:58:00Z", "parent_id": 2, "parent_name": "Mesh node", "group": "Living room"},
        {"id": 4, "name": "Printer", "ip": "192.168.0.60", "mac": None, "online": False, "type": "printer", "vendor": None,
         "last_seen": "2026-10-07T09:00:00Z", "parent_id": 1, "parent_name": "Router"},
        {"id": 5, "name": "NAS", "ip": "192.168.0.70", "mac": "aa:00:00:00:00:05", "online": True, "type": "nas", "vendor": "Synology",
         "last_seen": "2026-10-08T11:58:00Z", "parent_id": 1, "parent_name": "Router"},
    ],
}


@pytest.fixture
def summary():
    return copy.deepcopy(SUMMARY)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_netlens(aioclient_mock, summary):
    """Netlens answers /api/stats/summary with `summary` (mutate it in a test to change the answer)."""

    async def answer(method, url, data):
        return AiohttpClientMockResponse(method, url, json=summary)  # serialised per request, so tests can edit `summary`

    aioclient_mock.get(f"{URL}/api/stats/summary", side_effect=answer)
    return aioclient_mock


def make_entry(options=None, **data):
    return MockConfigEntry(
        domain=DOMAIN,
        title="Netlens",
        unique_id=URL,
        data={CONF_URL: URL, CONF_TOKEN: TOKEN, CONF_VERIFY_SSL: True, **data},
        options=options or {},
    )


@pytest.fixture(scope="session", autouse=True)
def _start_resolver_thread_once():
    """The DNS library starts a helper thread on first use; start it before the first test so the leak check ignores it."""
    try:
        import pycares

        pycares.Channel()
    except Exception:  # noqa: BLE001 - only a warm-up
        pass
    yield
