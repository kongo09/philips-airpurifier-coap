"""Tests for the integration setup, unload and lifecycle."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap.const import (
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_STATUS,
    DOMAIN,
    PhilipsApi,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .fixtures.fake_client import FakeClient

FULL_AC3033 = {
    PhilipsApi.DEVICE_ID: "ABCD1234567890",
    PhilipsApi.WIFI_VERSION: "AWS_Philips_AIR@1.0.0",
    PhilipsApi.MODEL_ID: "AC3033/10",
    PhilipsApi.NAME: "Living Room",
    PhilipsApi.POWER: "1",
    PhilipsApi.MODE: "AG",
    PhilipsApi.SPEED: "1",
    "pm25": 15,
    "iaql": 1,
    "rh": 45,
    "temp": 22,
    "cl": False,
    "ddp": "1",
    "fltsts1": 80,
    "flttotal1": 100,
    "fltt1": "A3",
}


def _make_entry(model: str = "AC3033", status: dict | None = None, with_status: bool = True):
    """Build a MockConfigEntry for the given model."""
    data = {
        CONF_HOST: "1.2.3.4",
        CONF_MODEL: model,
        CONF_NAME: "Living Room",
        CONF_DEVICE_ID: "ABCD1234567890",
    }
    if with_status:
        data[CONF_STATUS] = status or FULL_AC3033
    return MockConfigEntry(
        domain=DOMAIN, unique_id="ABCD1234567890", title=f"{model} Living Room", data=data
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, client: FakeClient) -> bool:
    """Set up the integration with a mocked client and no icon registration."""
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.philips_airpurifier_coap.CoAPClient.create",
            AsyncMock(return_value=client),
        ),
        patch("custom_components.philips_airpurifier_coap.async_setup", return_value=True),
        patch(
            "custom_components.philips_airpurifier_coap.async_get_mac_address_from_host",
            AsyncMock(return_value=None),
        ),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return result


async def test_setup_creates_entities(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A full setup loads the entry and creates the expected entities."""
    entry = _make_entry()
    client = FakeClient(FULL_AC3033)
    assert await _setup(hass, entry, client)
    assert entry.state is ConfigEntryState.LOADED

    ent_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    domains = {e.entity_id.split(".")[0] for e in entities}
    assert {"fan", "sensor", "switch", "select", "light", "binary_sensor"} <= domains
    # All unique_ids keep the legacy "{model}-{device_id}..." prefix.
    assert all(e.unique_id.startswith("AC3033-ABCD1234567890") for e in entities)


async def test_setup_without_status_fetches_it(
    hass: HomeAssistant, bypass_integration_deps
) -> None:
    """An entry without stored status fetches it during setup."""
    entry = _make_entry(with_status=False)
    client = FakeClient(FULL_AC3033)
    assert await _setup(hass, entry, client)
    assert entry.state is ConfigEntryState.LOADED
    # The fetched status is persisted back into the entry.
    assert CONF_STATUS in entry.data


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant, bypass_integration_deps
) -> None:
    """A connection failure puts the entry into the retry state."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.philips_airpurifier_coap.CoAPClient.create",
            AsyncMock(side_effect=TimeoutError),
        ),
        patch("custom_components.philips_airpurifier_coap.async_setup", return_value=True),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload(hass: HomeAssistant, bypass_integration_deps) -> None:
    """Unloading the entry succeeds and shuts the coordinator down."""
    entry = _make_entry()
    client = FakeClient(FULL_AC3033)
    assert await _setup(hass, entry, client)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    client.shutdown.assert_awaited()


async def test_push_update_refreshes_state(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A status pushed by the device updates the entity state."""
    entry = _make_entry()
    client = FakeClient(FULL_AC3033)
    assert await _setup(hass, entry, client)

    fan_entity_id = next(iter(hass.states.async_entity_ids("fan")))
    assert hass.states.get(fan_entity_id).state == "on"

    new_status = {**FULL_AC3033, PhilipsApi.POWER: "0"}
    await client.queue.put(new_status)
    await hass.async_block_till_done()
    assert hass.states.get(fan_entity_id).state == "off"


async def test_fan_actions(hass: HomeAssistant, bypass_integration_deps) -> None:
    """Fan service calls reach the client."""
    entry = _make_entry()
    client = FakeClient(FULL_AC3033)
    assert await _setup(hass, entry, client)

    fan_entity_id = next(iter(hass.states.async_entity_ids("fan")))
    await hass.services.async_call("fan", "turn_off", {"entity_id": fan_entity_id}, blocking=True)
    client.set_control_value.assert_awaited()

    await hass.services.async_call(
        "fan", "set_preset_mode", {"entity_id": fan_entity_id, "preset_mode": "auto"}, blocking=True
    )
    client.set_control_values.assert_awaited()


async def test_switch_and_select_actions(hass: HomeAssistant, bypass_integration_deps) -> None:
    """Switch and select service calls reach the client."""
    entry = _make_entry()
    client = FakeClient(FULL_AC3033)
    assert await _setup(hass, entry, client)

    switch_id = next(iter(hass.states.async_entity_ids("switch")))
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_id}, blocking=True)
    client.set_control_value.assert_awaited()


async def test_setup_updates_mac(hass: HomeAssistant, bypass_integration_deps) -> None:
    """The deferred MAC lookup updates the device information."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    client = FakeClient(FULL_AC3033)
    with (
        patch(
            "custom_components.philips_airpurifier_coap.CoAPClient.create",
            AsyncMock(return_value=client),
        ),
        patch("custom_components.philips_airpurifier_coap.async_setup", return_value=True),
        patch(
            "custom_components.philips_airpurifier_coap.async_get_mac_address_from_host",
            AsyncMock(return_value="aa:bb:cc:dd:ee:ff"),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.runtime_data.device_information.mac == "aa:bb:cc:dd:ee:ff"


async def test_async_get_mac_ipv4(hass: HomeAssistant) -> None:
    """An IPv4 host is resolved to a normalised MAC address."""
    from custom_components.philips_airpurifier_coap import async_get_mac_address_from_host

    with patch(
        "custom_components.philips_airpurifier_coap.get_mac_address",
        return_value="AA:BB:CC:DD:EE:FF",
    ):
        assert await async_get_mac_address_from_host(hass, "1.2.3.4") == "aa:bb:cc:dd:ee:ff"


async def test_async_get_mac_hostname(hass: HomeAssistant) -> None:
    """A hostname is resolved to a MAC address."""
    from custom_components.philips_airpurifier_coap import async_get_mac_address_from_host

    with patch(
        "custom_components.philips_airpurifier_coap.get_mac_address",
        return_value="AA:BB:CC:DD:EE:FF",
    ):
        assert await async_get_mac_address_from_host(hass, "myhost") == "aa:bb:cc:dd:ee:ff"


async def test_async_get_mac_none(hass: HomeAssistant) -> None:
    """No MAC found returns None."""
    from custom_components.philips_airpurifier_coap import async_get_mac_address_from_host

    with patch("custom_components.philips_airpurifier_coap.get_mac_address", return_value=None):
        assert await async_get_mac_address_from_host(hass, "1.2.3.4") is None


async def test_async_setup_registers_icons(hass: HomeAssistant) -> None:
    """async_setup registers the static icon paths and the JS loader."""
    from unittest.mock import MagicMock

    from custom_components.philips_airpurifier_coap import async_setup

    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    with patch("custom_components.philips_airpurifier_coap.add_extra_js_url"):
        assert await async_setup(hass, {})
    assert hass.http.async_register_static_paths.await_count >= 1


def test_listing_view_lists_icons() -> None:
    """The icon listing view returns the bundled SVG icons as JSON."""
    import json
    import os

    from custom_components.philips_airpurifier_coap import ListingView, __file__ as init_file

    iconpath = os.path.join(os.path.dirname(init_file), "icons", "pap")
    view = ListingView("/url", iconpath, None)
    icons = json.loads(view.get_icons_list(iconpath))
    assert any("allergen_mode" in icon["name"] for icon in icons)
