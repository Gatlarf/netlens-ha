from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.netlens.api import NetlensAuthError, NetlensConnectionError
from custom_components.netlens.const import CONF_DEVICES, CONF_SCAN_INTERVAL, CONF_TOKEN, CONF_TRACK_EVENTS, CONF_URL, CONF_VERIFY_SSL, DOMAIN
from .conftest import TOKEN, URL, make_entry

USER = {CONF_URL: "netlens.test:8080", CONF_TOKEN: TOKEN, CONF_VERIFY_SSL: True}


async def _start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def test_user_flow_creates_an_entry(hass, mock_netlens):
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: URL, CONF_TOKEN: TOKEN, CONF_VERIFY_SSL: True}
    assert result["title"] == "Netlens (netlens.test:8080)"
    assert result["result"].unique_id == URL


async def test_errors_are_shown_and_the_flow_can_continue(hass, aioclient_mock, summary):
    aioclient_mock.get(f"{URL}/api/stats/summary", status=401)
    result = await hass.config_entries.flow.async_configure((await _start(hass))["flow_id"], USER)
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", status=500)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", json={**summary, "api": 9})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["errors"] == {"base": "unsupported"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**USER, CONF_URL: "ftp://x"})
    assert result["errors"] == {"base": "invalid_url"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", json=summary)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_the_same_netlens_cannot_be_added_twice(hass, mock_netlens):
    make_entry().add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure((await _start(hass))["flow_id"], USER)
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"


async def test_reauth_updates_the_token(hass, aioclient_mock, summary):
    aioclient_mock.get(f"{URL}/api/stats/summary", json=summary)
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm" and result["description_placeholders"]["url"] == URL
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", status=401)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: "wrong"})
    assert result["errors"] == {"base": "invalid_auth"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", json=summary)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TOKEN: "fresh"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == "fresh"


async def test_options_flow_lists_devices_and_saves(hass, mock_netlens):
    entry = make_entry(options={CONF_DEVICES: ["aa:00:00:00:00:03", "gone-device"]})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    selector = next(v for k, v in result["data_schema"].schema.items() if k == CONF_DEVICES)
    values = {o["value"]: o["label"] for o in selector.config["options"]}
    assert values["aa:00:00:00:00:03"] == "Laptop (192.168.0.50)" and values["ip-192.168.0.60"] == "Printer (192.168.0.60)"
    assert values["gone-device"].endswith("(not in Netlens right now)")  # tracked but missing: still selectable

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 120, CONF_TRACK_EVENTS: False, CONF_DEVICES: ["aa:00:00:00:00:03"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SCAN_INTERVAL: 120, CONF_TRACK_EVENTS: False, CONF_DEVICES: ["aa:00:00:00:00:03"]}


async def test_reconfigure_changes_the_token_and_keeps_it_when_left_empty(hass, aioclient_mock, summary):
    aioclient_mock.get(f"{URL}/api/stats/summary", json=summary)
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", status=401)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL, CONF_TOKEN: "nl_bad", CONF_VERIFY_SSL: True})
    assert result["errors"] == {"base": "invalid_auth"} and entry.data[CONF_TOKEN] == TOKEN

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/stats/summary", json=summary)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL, CONF_TOKEN: "nl_fresh", CONF_VERIFY_SSL: True})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_TOKEN] == "nl_fresh"

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL, CONF_VERIFY_SSL: True})
    assert result["reason"] == "reconfigure_successful" and entry.data[CONF_TOKEN] == "nl_fresh"  # empty token = unchanged


async def test_reconfigure_can_move_to_a_new_address_but_not_onto_another_entry(hass, aioclient_mock, summary):
    new = "http://new-netlens.test:8080"
    aioclient_mock.get(f"{URL}/api/stats/summary", json=summary)
    aioclient_mock.get(f"{new}/api/stats/summary", json=summary)
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: "new-netlens.test:8080", CONF_VERIFY_SSL: True})
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_URL] == new and entry.unique_id == new and entry.title == "Netlens (new-netlens.test:8080)"

    other = make_entry()
    other.add_to_hass(hass)  # a second entry that owns the old address
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL, CONF_VERIFY_SSL: True})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"
