"""AC3420 target humidity controls only the humidity setting."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap import humidifier, number
from custom_components.philips_airpurifier_coap.config_entry_data import ConfigEntryData
from custom_components.philips_airpurifier_coap.const import DOMAIN, PhilipsApi
from custom_components.philips_airpurifier_coap.model import DeviceInformation


@pytest.fixture
def device(hass):
    """Create a model with mocked control writes."""

    def create(model, **status):
        state = {
            PhilipsApi.MODEL_ID: model,
            PhilipsApi.DEVICE_ID: "test-device",
            PhilipsApi.WIFI_VERSION: "test-firmware",
            PhilipsApi.NEW2_POWER: 0,
            "D03128": 60,
            **status,
        }
        client = Mock(set_control_value=AsyncMock(return_value=True))
        coordinator = Mock(status=state, client=client)
        data = ConfigEntryData(
            DeviceInformation(model, "Test device", "test-device", "device.invalid"),
            client,
            coordinator,
            state,
        )
        entry = MockConfigEntry(domain=DOMAIN, data={})
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
        return entry, data

    return create


@pytest.mark.parametrize("model, expected", [("AC3420", 1), ("AC3421", 0)])
async def test_target_humidity_is_scoped_to_ac3420(hass, device, model, expected):
    """The inherited AC3421 platform remains unchanged."""
    entry, _ = device(model)
    entities = []
    await number.async_setup_entry(hass, entry, lambda added, **kwargs: entities.extend(added))
    assert len(entities) == expected
    if expected:
        target = entities[0]
        assert target.translation_key == "target_humidity"
        assert target.entity_category is None
        assert (target.native_min_value, target.native_max_value, target.native_step) == (40, 70, 10)
        assert target.native_unit_of_measurement == "%"
        assert target.icon == "mdi:water-percent"


@pytest.mark.parametrize("power", [0, 1])
async def test_target_humidity_writes_do_not_toggle_power(hass, device, power):
    """A target-only control writes only D03128."""
    entry, data = device("AC3420", D03102=power)
    target = number.PhilipsNumber(hass, entry, data, "D03128")
    target._handle_coordinator_update = Mock()
    await target.async_set_native_value(50)
    data.client.set_control_value.assert_awaited_once_with("D03128", 50)
    assert data.coordinator.status["D03102"] == power
    data.coordinator.status["D03128"] = 70
    assert target.native_value == 70


@pytest.mark.parametrize("model, enabled", [("AC3420", False), ("AC3421", True)])
async def test_legacy_humidifier_remains_for_existing_automations(hass, device, model, enabled):
    """Only new AC3420 registrations omit the duplicate control by default."""
    entry, _ = device(model)
    entities = []
    await humidifier.async_setup_entry(hass, entry, lambda added, **kwargs: entities.extend(added))
    assert len(entities) == 1
    assert entities[0].entity_registry_enabled_default is enabled
    assert entities[0].unique_id == f"{model}-test-device-d03128#1"


def test_target_humidity_has_english_name_and_icon():
    """The new number has matching English catalog and icon entries."""
    root = Path(__file__).parents[1] / "custom_components" / DOMAIN
    english = json.loads((root / "strings.json").read_text(encoding="utf-8"))
    assert english == json.loads((root / "translations/en.json").read_text(encoding="utf-8"))
    assert english["entity"]["number"]["target_humidity"]["name"] == "Target humidity"
    icons = json.loads((root / "icons.json").read_text(encoding="utf-8"))
    assert icons["entity"]["number"]["target_humidity"]["default"] == "mdi:water-percent"
