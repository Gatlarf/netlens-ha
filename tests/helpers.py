from datetime import timedelta

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.netlens.const import DOMAIN


async def setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def entity_id(hass, entry, platform, key):
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert found is not None, f"no {platform} entity with unique id {key}"
    return found


def state(hass, entry, platform, key):
    return hass.states.get(entity_id(hass, entry, platform, key))


async def poll(hass, freezer, seconds=61):
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
