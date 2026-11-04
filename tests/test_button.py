"""Tests for the filter reset buttons."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap.button import (
    PhilipsFilterResetButton,
    async_setup_entry,
)
from custom_components.philips_airpurifier_coap.const import DOMAIN
from custom_components.philips_airpurifier_coap.model import DeviceInformation

# Filter part of the status reported by an AC0951/13 with expired filters
AC0951_STATUS = {
    "D01S03": "My Device",
    "D01S05": "AC0951/13",
    "DeviceId": "0123456789abcdef",
    "WifiVersion": "AWS_Philips_AIR_Combo@86",
    "D05207": 720,
    "D05408": 9600,
    "D0520D": 0,
    "D0540E": 0,
}


def _config_entry_data(model: str, status: dict) -> SimpleNamespace:
    coordinator = SimpleNamespace(status=status, client=MagicMock())
    coordinator.client.set_control_value = AsyncMock()
    return SimpleNamespace(
        device_information=DeviceInformation(
            model=model, name="My Device", device_id="0123456789abcdef", host="192.0.2.1"
        ),
        coordinator=coordinator,
        latest_status=status,
    )


async def _setup_buttons(hass: HomeAssistant, model: str, status: dict) -> list[PhilipsFilterResetButton]:
    entry = MockConfigEntry(domain=DOMAIN)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _config_entry_data(model, status)
    buttons: list[PhilipsFilterResetButton] = []
    await async_setup_entry(hass, entry, lambda entities, update_before_add: buttons.extend(entities))
    return buttons


async def test_ac0951_has_filter_reset_buttons(hass: HomeAssistant) -> None:
    """AC0951 gets a reset button for the pre-filter and the NanoProtect filter."""
    buttons = await _setup_buttons(hass, "AC0951", dict(AC0951_STATUS))

    assert sorted(button.translation_key for button in buttons) == [
        "reset_nanoprotect_filter",
        "reset_pre_filter",
    ]


async def test_no_button_without_total(hass: HomeAssistant) -> None:
    """No button is created if the device does not report the filter total."""
    status = dict(AC0951_STATUS)
    del status["D05408"]

    buttons = await _setup_buttons(hass, "AC0951", status)

    assert [button.translation_key for button in buttons] == ["reset_pre_filter"]


async def test_no_buttons_for_other_models(hass: HomeAssistant) -> None:
    """Models without AVAILABLE_FILTER_RESETS get no buttons."""
    buttons = await _setup_buttons(hass, "AC1715", dict(AC0951_STATUS))

    assert buttons == []


async def test_press_resets_counter_to_total(hass: HomeAssistant) -> None:
    """Pressing the button writes the filter total into the filter counter."""
    status = dict(AC0951_STATUS)
    buttons = await _setup_buttons(hass, "AC0951", status)
    button = next(b for b in buttons if b.translation_key == "reset_nanoprotect_filter")
    button.async_write_ha_state = MagicMock()

    await button.async_press()

    button.coordinator.client.set_control_value.assert_awaited_once_with("D0540E", 9600)
    assert status["D0540E"] == 9600
