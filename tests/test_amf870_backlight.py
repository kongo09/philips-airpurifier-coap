"""AMF870 display brightness uses the physical backlight field."""

from unittest.mock import AsyncMock, Mock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap.config_entry_data import ConfigEntryData
from custom_components.philips_airpurifier_coap.const import DOMAIN, PhilipsApi
from custom_components.philips_airpurifier_coap.light import PhilipsLight
from custom_components.philips_airpurifier_coap.model import DeviceInformation


def make_light(hass, model):
    """Create a display entity with a mocked transport."""
    status = {
        PhilipsApi.NEW2_POWER: 0,
        PhilipsApi.NEW2_DISPLAY_BACKLIGHT: 100,
        PhilipsApi.AMF870_DISPLAY_BACKLIGHT: 20,
    }
    client = Mock(set_control_value=AsyncMock(return_value=True))
    coordinator = Mock(status=status, client=client)
    data = ConfigEntryData(
        DeviceInformation(model, "Test device", "test-device", "device.invalid"),
        client,
        coordinator,
        status,
    )
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    return PhilipsLight(hass, entry, data, PhilipsApi.NEW2_DISPLAY_BACKLIGHT), data


async def test_amf870_uses_physical_field_and_preserves_unique_id(hass):
    """Backlight reads and writes D0312F while keeping its registered ID."""
    light, data = make_light(hass, "AMF870")
    light._handle_coordinator_update = Mock()
    assert light.brightness == 51
    assert light.unique_id == "AMF870-test-device-d0312d"
    await light.async_turn_on(brightness=178)
    data.client.set_control_value.assert_awaited_once_with("D0312F", 70)
    assert data.coordinator.status["D0312D"] == 100
    await light.async_turn_off()
    data.client.set_control_value.assert_awaited_with("D0312F", 0)
    assert not light.is_on


def test_other_models_keep_original_display_field(hass):
    """An untested sibling keeps the existing light protocol field."""
    light, _ = make_light(hass, "AMF765")
    assert light.kind == "D0312D"
    assert light.brightness == 255
