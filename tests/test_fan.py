"""Tests for the fan platform."""

import pytest

from custom_components.philips_airpurifier_coap import fan
from custom_components.philips_airpurifier_coap.const import PhilipsApi
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def _setup(hass: HomeAssistant, make_runtime, model: str, status: dict | None = None):
    """Run the fan platform setup and return the created entities."""
    entry, runtime = make_runtime(model=model, status=status)
    added: list = []
    await fan.async_setup_entry(hass, entry, lambda entities, *_: added.extend(entities))
    return added, runtime


async def test_fan_created_with_unique_id(hass: HomeAssistant, make_runtime) -> None:
    """A standard model creates exactly one fan with a model-based unique_id."""
    entities, _ = await _setup(hass, make_runtime, "AC3033")
    assert len(entities) == 1
    assert entities[0].unique_id == "AC3033-ABCD1234567890"


async def test_fan_is_on(hass: HomeAssistant, make_runtime) -> None:
    """The fan reports on/off from the power key."""
    status = {
        PhilipsApi.DEVICE_ID: "ABCD1234567890",
        PhilipsApi.WIFI_VERSION: "v",
        PhilipsApi.POWER: "1",
    }
    entities, _ = await _setup(hass, make_runtime, "AC3033", status)
    assert entities[0].is_on is True


async def test_fan_not_created_when_create_fan_false(hass: HomeAssistant, make_runtime) -> None:
    """Humidifier-only models (CREATE_FAN=False) do not create a fan entity."""
    status = {PhilipsApi.DEVICE_ID: "ABCD1234567890", PhilipsApi.WIFI_VERSION: "v"}
    entities, _ = await _setup(hass, make_runtime, "HU1509", status)
    assert entities == []


async def test_fan_turn_on_raises_on_client_error(hass: HomeAssistant, make_runtime) -> None:
    """A client failure when turning the fan on surfaces as HomeAssistantError."""
    entities, runtime = await _setup(hass, make_runtime, "AC3033")
    runtime.client.set_control_value.side_effect = OSError("boom")
    with pytest.raises(HomeAssistantError):
        await entities[0].async_turn_on()


@pytest.mark.parametrize("model", ["AC2210", "AC2220", "AC2221", "AC3021"])
async def test_newly_supported_models(hass: HomeAssistant, make_runtime, model: str) -> None:
    """Models ported from upstream create a fan with the expected unique_id."""
    status = {PhilipsApi.DEVICE_ID: "ABCD1234567890", PhilipsApi.WIFI_VERSION: "v"}
    entities, _ = await _setup(hass, make_runtime, model, status)
    assert len(entities) == 1
    assert entities[0].unique_id == f"{model}-ABCD1234567890"
    assert entities[0].preset_modes  # the ported preset map is wired up


async def test_fan_unsupported_model_creates_nothing(hass: HomeAssistant, make_runtime) -> None:
    """An unknown model logs an error and creates no fan entity."""
    entry, runtime = make_runtime(model="AC3033")
    runtime.device_information.model = "UNKNOWN9999"
    added: list = []
    await fan.async_setup_entry(hass, entry, lambda entities, *_: added.extend(entities))
    assert added == []
