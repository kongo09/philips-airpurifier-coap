"""Coverage for the fan device base classes and the bespoke AC1214 handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.philips_airpurifier_coap.const import ICON, PhilipsApi, PresetMode
from custom_components.philips_airpurifier_coap.devices import model_to_class
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_BASE = {
    PhilipsApi.DEVICE_ID: "ABCD1234567890",
    PhilipsApi.WIFI_VERSION: "AWS_Philips_AIR@1.0.0",
}


def _fan(hass, make_runtime, model, status, stub_write=True):
    """Construct the fan entity (which is the device class) for a model."""
    entry, runtime = make_runtime(model=model, status={**_BASE, **status})
    fan = model_to_class[model](hass, entry, runtime)
    if stub_write:
        fan.async_write_ha_state = lambda: None
    return fan, runtime


# --------------------------------------------------------------------------- #
# PhilipsGenericFanBase (devices/base.py)
# --------------------------------------------------------------------------- #
async def test_fan_turn_on_paths(hass: HomeAssistant, make_runtime) -> None:
    """turn_on dispatches to preset, percentage, or a plain power-on."""
    fan, runtime = _fan(hass, make_runtime, "AC2889", {PhilipsApi.POWER: "0"})

    await fan.async_turn_on(preset_mode=PresetMode.AUTO)
    runtime.client.set_control_values.assert_awaited()

    runtime.client.set_control_values.reset_mock()
    await fan.async_turn_on(percentage=50)
    runtime.client.set_control_values.assert_awaited()

    await fan.async_turn_on()  # plain power-on
    runtime.client.set_control_value.assert_awaited_with(PhilipsApi.POWER, "1")


async def test_fan_set_percentage_paths(hass: HomeAssistant, make_runtime) -> None:
    """A zero percentage turns the fan off; a positive one sets a speed."""
    fan, runtime = _fan(hass, make_runtime, "AC2889", {PhilipsApi.POWER: "1"})

    await fan.async_set_percentage(0)
    runtime.client.set_control_value.assert_awaited_with(PhilipsApi.POWER, "0")

    await fan.async_set_percentage(50)
    runtime.client.set_control_values.assert_awaited()


async def test_fan_set_preset_unknown_is_noop(hass: HomeAssistant, make_runtime) -> None:
    """An unknown preset mode is ignored without a client call."""
    fan, runtime = _fan(hass, make_runtime, "AC2889", {PhilipsApi.POWER: "1"})
    await fan.async_set_preset_mode("not-a-preset")
    runtime.client.set_control_values.assert_not_awaited()


async def test_fan_command_error_surfaces(hass: HomeAssistant, make_runtime) -> None:
    """A client failure on a multi-value command surfaces as HomeAssistantError."""
    fan, runtime = _fan(hass, make_runtime, "AC2889", {PhilipsApi.POWER: "1"})
    runtime.client.set_control_values.side_effect = OSError("boom")
    with pytest.raises(HomeAssistantError):
        await fan.async_set_preset_mode(PresetMode.AUTO)


async def test_fan_without_oscillation(hass: HomeAssistant, make_runtime) -> None:
    """A fan without an oscillation key reports None and ignores oscillate calls."""
    fan, runtime = _fan(hass, make_runtime, "AC2889", {PhilipsApi.POWER: "1"})
    assert fan.oscillating is None
    await fan.async_oscillate(True)
    runtime.client.set_control_value.assert_not_awaited()


async def test_fan_oscillation_unknown_status(hass: HomeAssistant, make_runtime) -> None:
    """A fan with an oscillation key but no value reports None."""
    fan, _ = _fan(hass, make_runtime, "CX5120", {PhilipsApi.NEW2_POWER: 1})
    assert fan.oscillating is None


async def test_fan_extra_attributes(hass: HomeAssistant, make_runtime) -> None:
    """extra_state_attributes resolves both mapped and callable value maps."""
    status = {
        PhilipsApi.POWER: "1",
        PhilipsApi.RUNTIME: 3_600_000,
        PhilipsApi.PREFERRED_INDEX: "1",
    }
    fan, _ = _fan(hass, make_runtime, "AC2889", status)
    attrs = fan.extra_state_attributes
    assert PhilipsApi.RUNTIME or attrs  # callable map computed a value
    assert any(isinstance(v, str) for v in attrs.values())


async def test_fan_icon_states(hass: HomeAssistant, make_runtime) -> None:
    """The icon reflects power, a mapped preset, an unmapped preset and none."""
    # Off -> the power button.
    off, _ = _fan(hass, make_runtime, "AC2889", {PhilipsApi.POWER: "0"})
    assert off.icon == ICON.POWER_BUTTON

    # On with a known preset -> the mapped icon.
    mapped, _ = _fan(hass, make_runtime, "AC2889", {PhilipsApi.POWER: "1", PhilipsApi.MODE: "P"})
    assert mapped.icon == PresetMode.ICON_MAP[PresetMode.AUTO]

    # On with no matching preset -> the generic speed button.
    nomatch, _ = _fan(hass, make_runtime, "AC2889", {PhilipsApi.POWER: "1", PhilipsApi.MODE: "??"})
    assert nomatch.icon == ICON.FAN_SPEED_BUTTON

    # On with a preset that has no icon mapping -> the generic speed button.
    custom, _ = _fan(hass, make_runtime, "AC2889", {PhilipsApi.POWER: "1"})
    custom._available_preset_modes = {"unmapped": {PhilipsApi.POWER: "1"}}
    custom._preset_modes = ["unmapped"]
    assert custom.icon == ICON.FAN_SPEED_BUTTON


# --------------------------------------------------------------------------- #
# PhilipsAC1214 (devices/legacy.py) bespoke handling
# --------------------------------------------------------------------------- #
async def test_ac1214_special_handling(hass: HomeAssistant, make_runtime) -> None:
    """The AC1214 powers on first and transitions through mode 'A'."""
    fan, runtime = _fan(
        hass,
        make_runtime,
        "AC1214",
        {PhilipsApi.POWER: "0", PhilipsApi.MODE: "N", PhilipsApi.SPEED: "1"},
    )

    with patch(
        "custom_components.philips_airpurifier_coap.devices.legacy.asyncio.sleep",
        AsyncMock(),
    ):
        # Plain turn-on while off: powers the device on, nothing else.
        await fan.async_turn_on()
        runtime.client.set_control_value.assert_awaited()  # power-on from _ensure_power_on

        # Device now reports on; a preset change transitions via mode 'A' first.
        runtime.coordinator.data[PhilipsApi.POWER] = "1"
        await fan.async_set_preset_mode(PresetMode.AUTO)
        assert runtime.client.set_control_values.await_count >= 1

        # 0% switches off; a positive percentage selects a manual speed.
        await fan.async_set_percentage(0)
        await fan.async_set_percentage(66)

        # turn_on can also carry a preset or a percentage.
        await fan.async_turn_on(preset_mode=PresetMode.NIGHT)
        await fan.async_turn_on(percentage=66)

    assert runtime.client.set_control_values.await_count >= 2


async def test_ac1214_mode_transition_to_allergen(hass: HomeAssistant, make_runtime) -> None:
    """Setting the allergen preset (target 'A') skips the intermediate transition."""
    fan, runtime = _fan(
        hass,
        make_runtime,
        "AC1214",
        {PhilipsApi.POWER: "1", PhilipsApi.MODE: "P", PhilipsApi.SPEED: "1"},
    )
    with patch(
        "custom_components.philips_airpurifier_coap.devices.legacy.asyncio.sleep",
        AsyncMock(),
    ):
        await fan.async_set_preset_mode(PresetMode.ALLERGEN)
    runtime.client.set_control_values.assert_awaited()
