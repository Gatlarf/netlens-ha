import aiohttp
import pytest

from custom_components.netlens.api import (
    NetlensApi,
    NetlensApiVersionError,
    NetlensAuthError,
    NetlensConnectionError,
    normalize_url,
)

URL = "http://netlens.test:8080"


@pytest.mark.parametrize("raw,expected", [
    ("192.168.0.189:8080", "http://192.168.0.189:8080"),
    (" http://nl.lan:8080/ ", "http://nl.lan:8080"),
    ("https://nl.example.com/netlens/", "https://nl.example.com/netlens"),
])
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize("bad", ["", "ftp://x", "http://"])
def test_normalize_url_rejects(bad):
    with pytest.raises(ValueError):
        normalize_url(bad)


async def test_summary_sends_the_token(hass, aioclient_mock, summary):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    aioclient_mock.get(f"{URL}/api/stats/summary", json=summary)
    api = NetlensApi(async_get_clientsession(hass), URL, "tok")
    assert (await api.summary())["devices"]["total"] == 5
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer tok"


@pytest.mark.parametrize("status,error", [(401, NetlensAuthError), (404, NetlensApiVersionError), (500, NetlensConnectionError)])
async def test_http_errors(hass, aioclient_mock, status, error):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    aioclient_mock.get(f"{URL}/api/stats/summary", status=status)
    with pytest.raises(error):
        await NetlensApi(async_get_clientsession(hass), URL, "t").summary()


async def test_not_json_and_wrong_api_version_and_unreachable(hass, aioclient_mock, summary):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    aioclient_mock.get(f"{URL}/api/stats/summary", text="<html>nope</html>")
    with pytest.raises(NetlensConnectionError, match="not JSON"):
        await NetlensApi(session, URL, "t").summary()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", json={**summary, "api": 2})
    with pytest.raises(NetlensApiVersionError, match="unsupported"):
        await NetlensApi(session, URL, "t").summary()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", exc=aiohttp.ClientError("refused"))
    with pytest.raises(NetlensConnectionError, match="cannot connect"):
        await NetlensApi(session, URL, "t").summary()


async def test_events_are_sorted_oldest_first(hass, aioclient_mock):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    aioclient_mock.get(f"{URL}/api/events", json=[{"id": 9}, {"id": 7}, {"id": 8}])
    events = await NetlensApi(async_get_clientsession(hass), URL, "t").events(6)
    assert [e["id"] for e in events] == [7, 8, 9]
    assert "since_id=6" in str(aioclient_mock.mock_calls[0][1])
