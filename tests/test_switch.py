"""Tests for the switch platform."""

import pytest

from custom_components.philips_airpurifier_coap import switch
from custom_components.philips_airpurifier_coap.const import PhilipsApi
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def _setup(hass: HomeAssistant, make_runtime, model: str, status: dict | None = None):
    """Run the switch platform setup and return the created entities."""
    entry, runtime = make_runtime(model=model, status=status)
    added: list = []
    await switch.async_setup_entry(hass, entry, lambda entities, *_: added.extend(entities))
    return added, runtime


async def test_switch_created_for_legacy_model(hass: HomeAssistant, make_runtime) -> None:
    """A legacy model exposes its child lock switch with a stable unique_id."""
    entities, _ = await _setup(hass, make_runtime, "AC3033")

    assert len(entities) == 1
    child_lock = entities[0]
    assert child_lock.entity_description.key == PhilipsApi.CHILD_LOCK
    assert child_lock.unique_id == "AC3033-ABCD1234567890-cl"
    assert child_lock.entity_description.entity_category == EntityCategory.CONFIG
    assert child_lock.translation_key == "child_lock"


async def test_switch_created_for_new2_model(hass: HomeAssistant, make_runtime) -> None:
    """A new2 model exposes several switches."""
    entities, _ = await _setup(hass, make_runtime, "AMF870")

    keys = {entity.entity_description.key for entity in entities}
    assert keys == {
        PhilipsApi.NEW2_CHILD_LOCK,
        PhilipsApi.NEW2_BEEP,
        PhilipsApi.NEW2_STANDBY_SENSORS,
        PhilipsApi.NEW2_AUTO_PLUS_AI,
    }


async def test_switch_is_on_reflects_status(hass: HomeAssistant, make_runtime) -> None:
    """is_on compares against the configured off value."""
    status = {**dict_status(), PhilipsApi.CHILD_LOCK: True}
    entities, _ = await _setup(hass, make_runtime, "AC3033", status)
    assert entities[0].is_on is True

    status = {**dict_status(), PhilipsApi.CHILD_LOCK: False}
    entities, _ = await _setup(hass, make_runtime, "AC3033", status)
    assert entities[0].is_on is False


async def test_switch_is_on_none_when_key_absent(hass: HomeAssistant, make_runtime) -> None:
    """is_on returns None (unknown) when the key is missing from the status."""
    entities, _ = await _setup(hass, make_runtime, "AC3033")
    assert entities[0].is_on is None


async def test_switch_turn_on_raises_on_client_error(hass: HomeAssistant, make_runtime) -> None:
    """A client failure during an action must surface as HomeAssistantError."""
    entities, runtime = await _setup(hass, make_runtime, "AMF870")
    runtime.client.set_control_value.side_effect = OSError("boom")

    with pytest.raises(HomeAssistantError):
        await entities[0].async_turn_on()


def dict_status() -> dict:
    """Return a minimal status that satisfies the entity DeviceInfo lookups."""
    return {
        PhilipsApi.DEVICE_ID: "ABCD1234567890",
        PhilipsApi.WIFI_VERSION: "AWS_Philips_AIR@1.0.0",
    }
