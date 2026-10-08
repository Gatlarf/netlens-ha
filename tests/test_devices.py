from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.netlens.const import CONF_DEVICES, DOMAIN
from .conftest import make_entry
from .helpers import entity_id, poll, setup, state

LAPTOP, NODE, ROUTER, PRINTER = "aa:00:00:00:00:03", "aa:00:00:00:00:02", "aa:00:00:00:00:01", "ip-192.168.0.60"


def device(hass, entry, key):
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{entry.entry_id}_{key}")})


async def test_no_device_entities_by_default(hass, mock_netlens):
    entry = make_entry()
    await setup(hass, entry)
    registry = er.async_get(hass)
    assert not [e for e in er.async_entries_for_config_entry(registry, entry.entry_id) if "_dev_" in e.unique_id]
    assert device(hass, entry, LAPTOP) is None


async def test_tracked_devices_get_a_presence_sensor_and_attributes(hass, mock_netlens):
    entry = make_entry(options={CONF_DEVICES: [LAPTOP, PRINTER]})
    await setup(hass, entry)
    laptop = hass.states.get(entity_id(hass, entry, "binary_sensor", f"dev_{LAPTOP}"))
    assert laptop.state == "on" and laptop.name == "Laptop" and laptop.attributes["device_class"] == "connectivity"
    assert laptop.attributes["ip"] == "192.168.0.50" and laptop.attributes["vendor"] == "Dell" and laptop.attributes["parent_name"] == "Mesh node"
    printer = hass.states.get(entity_id(hass, entry, "binary_sensor", f"dev_{PRINTER}"))  # no MAC: keyed by its IP
    assert printer.state == "off" and printer.attributes["mac"] is None
    # an untracked device has nothing
    assert er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_dev_{NODE}") is None


async def test_device_registry_mirrors_the_hierarchy(hass, mock_netlens):
    entry = make_entry(options={CONF_DEVICES: [ROUTER, NODE, LAPTOP, PRINTER]})
    await setup(hass, entry)
    registry = dr.async_get(hass)
    hub, router, node, laptop, printer = (registry.async_get_device(identifiers={(DOMAIN, k)}) for k in
                                          (entry.entry_id, *(f"{entry.entry_id}_{x}" for x in (ROUTER, NODE, LAPTOP, PRINTER))))
    assert router.via_device_id == hub.id  # the top level hangs below the hub
    assert node.via_device_id == router.id and laptop.via_device_id == node.id and printer.via_device_id == router.id
    assert laptop.name == "Laptop" and laptop.manufacturer == "Dell" and laptop.model == "pc"
    assert (dr.CONNECTION_NETWORK_MAC, LAPTOP) in laptop.connections and laptop.configuration_url.endswith("/#/device/3")


async def test_a_device_whose_parent_is_not_tracked_hangs_below_the_hub(hass, mock_netlens):
    entry = make_entry(options={CONF_DEVICES: [LAPTOP]})
    await setup(hass, entry)
    registry = dr.async_get(hass)
    assert device(hass, entry, LAPTOP).via_device_id == registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)}).id


async def test_presence_follows_netlens(hass, mock_netlens, summary, freezer):
    entry = make_entry(options={CONF_DEVICES: [LAPTOP]})
    await setup(hass, entry)
    summary["device_list"][2]["online"] = False
    await poll(hass, freezer)
    assert state(hass, entry, "binary_sensor", f"dev_{LAPTOP}").state == "off"


async def test_a_device_deleted_in_netlens_becomes_unavailable_and_returns(hass, mock_netlens, summary, freezer):
    entry = make_entry(options={CONF_DEVICES: [LAPTOP]})
    await setup(hass, entry)
    gone = summary["device_list"].pop(2)
    await poll(hass, freezer)
    assert state(hass, entry, "binary_sensor", f"dev_{LAPTOP}").state == "unavailable"
    summary["device_list"].insert(2, gone)
    await poll(hass, freezer)
    assert state(hass, entry, "binary_sensor", f"dev_{LAPTOP}").state == "on"


async def test_a_tracked_device_that_appears_later_gets_its_entity(hass, mock_netlens, summary, freezer):
    late = summary["device_list"].pop(2)
    entry = make_entry(options={CONF_DEVICES: [LAPTOP]})
    await setup(hass, entry)
    assert er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_dev_{LAPTOP}") is None
    summary["device_list"].insert(2, late)
    await poll(hass, freezer)
    assert state(hass, entry, "binary_sensor", f"dev_{LAPTOP}").state == "on"


async def test_renaming_in_netlens_updates_the_device(hass, mock_netlens, summary, freezer):
    entry = make_entry(options={CONF_DEVICES: [LAPTOP]})
    await setup(hass, entry)
    summary["device_list"][2]["name"] = "Bert's laptop"
    await poll(hass, freezer)
    assert device(hass, entry, LAPTOP).name == "Bert's laptop"


async def test_untracking_removes_entities_and_devices(hass, mock_netlens):
    entry = make_entry(options={CONF_DEVICES: [LAPTOP, ROUTER]})
    await setup(hass, entry)
    assert device(hass, entry, ROUTER) is not None
    hass.config_entries.async_update_entry(entry, options={CONF_DEVICES: [LAPTOP]})
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_dev_{ROUTER}") is None
    assert registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_dev_{LAPTOP}") is not None
    assert device(hass, entry, ROUTER) is None and device(hass, entry, LAPTOP) is not None
