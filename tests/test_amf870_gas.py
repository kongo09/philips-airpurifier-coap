"""AMF870 gas readings are categorical levels."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap.config_entry_data import ConfigEntryData
from custom_components.philips_airpurifier_coap.const import DOMAIN, PhilipsApi
from custom_components.philips_airpurifier_coap.model import DeviceInformation
from custom_components.philips_airpurifier_coap.sensor import PhilipsSensor


def make_gas_sensor(hass, model, value):
    """Create a gas sensor with a mocked coordinator."""
    status = {PhilipsApi.NEW2_GAS: value}
    client = Mock()
    coordinator = Mock(status=status, client=client)
    data = ConfigEntryData(
        DeviceInformation(model, "Test device", "test-device", "device.invalid"),
        client,
        coordinator,
        status,
    )
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    return PhilipsSensor(hass, entry, data, PhilipsApi.NEW2_GAS)


@pytest.mark.parametrize("value", [1, 2, 3, 4, 0, 5, None, True, "2", 2.5])
def test_amf870_levels_have_no_numeric_unit(hass, value):
    """Only integer levels 1-4 become enum states."""
    sensor = make_gas_sensor(hass, "AMF870", value)
    expected = f"L{value}" if type(value) is int and 1 <= value <= 4 else None
    assert sensor.native_value == expected
    assert sensor.device_class == SensorDeviceClass.ENUM
    assert sensor.options == ["L1", "L2", "L3", "L4"]
    assert sensor.state_class is None
    assert sensor.native_unit_of_measurement is None
    assert sensor.translation_key == "gas_level"
    assert sensor.unique_id == "AMF870-test-device-d03122"


def test_other_models_keep_numeric_gas_description(hass):
    """The per-model conversion leaves shared descriptions untouched."""
    sensor = make_gas_sensor(hass, "AC3737", 1)
    assert sensor.native_value == 1
    assert sensor.native_unit_of_measurement == "L"


def test_gas_level_translation_and_icon_keys():
    """The existing gas-level entity has catalog entries in every shipped locale."""
    root = Path(__file__).parents[1] / "custom_components" / DOMAIN
    for path in [root / "strings.json", root / "icons.json", *(root / "translations").glob("*.json")]:
        entity = json.loads(path.read_text(encoding="utf-8")).get("entity")
        if not entity:
            continue
        assert "gas_level" in entity["sensor"]
        assert "gas_level" in entity["select"]["preferred_index"]["state"]
    icons = json.loads((root / "icons.json").read_text(encoding="utf-8"))
    assert icons["entity"]["fan"]["pap"]["state_attributes"]["preset_mode"]["state"]["gas"] == "mdi:molecule"
