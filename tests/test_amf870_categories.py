"""AMF870 entity categories keep daily controls visible."""

from unittest.mock import Mock

from homeassistant.const import EntityCategory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap.config_entry_data import ConfigEntryData
from custom_components.philips_airpurifier_coap.const import DOMAIN, PhilipsApi
from custom_components.philips_airpurifier_coap.model import DeviceInformation
from custom_components.philips_airpurifier_coap.number import PhilipsNumber
from custom_components.philips_airpurifier_coap.select import PhilipsSelect
from custom_components.philips_airpurifier_coap.switch import PhilipsSwitch


def make_device(hass, model):
    """Create model data for entity constructor tests."""
    client = Mock()
    status = {}
    coordinator = Mock(status=status, client=client)
    data = ConfigEntryData(
        DeviceInformation(model, "Test device", "test-device", "device.invalid"),
        client,
        coordinator,
        status,
    )
    entry = MockConfigEntry(domain=DOMAIN, data={})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data
    return entry, data


def test_amf870_categories_keep_timer_in_configuration(hass):
    """Daily controls move out of configuration while Timer stays there."""
    entry, data = make_device(hass, "AMF870")
    for key in (PhilipsApi.NEW2_OSCILLATION, PhilipsApi.NEW2_TARGET_TEMP):
        assert PhilipsNumber(hass, entry, data, key).entity_category is None
    assert PhilipsSelect(hass, entry, data, PhilipsApi.NEW2_HEATING).entity_category is None
    assert PhilipsSelect(hass, entry, data, PhilipsApi.NEW2_TIMER).entity_category == EntityCategory.CONFIG
    for key in (PhilipsApi.NEW2_AUTO_PLUS_AI, PhilipsApi.NEW2_STANDBY_SENSORS):
        assert PhilipsSwitch(hass, entry, data, key).entity_category == EntityCategory.CONFIG


def test_other_model_keeps_existing_categories(hass):
    """The category override is limited to AMF870."""
    entry, data = make_device(hass, "AMF765")
    assert PhilipsNumber(hass, entry, data, PhilipsApi.NEW2_OSCILLATION).entity_category == EntityCategory.CONFIG
    assert PhilipsSelect(hass, entry, data, PhilipsApi.NEW2_HEATING).entity_category == EntityCategory.CONFIG
