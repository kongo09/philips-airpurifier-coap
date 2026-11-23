"""Tests for DHCP discovery of already configured devices and host changes."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap.const import (
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_STATUS,
    DOMAIN,
)

DEVICE_ID = "3ce4a4babfcb11f0967ad971360d8d3d"
MAC = "d0:ba:e4:4c:37:6b"
OLD_HOST = "192.168.2.166"
NEW_HOST = "192.168.2.167"

CLIENT_CREATE = "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create"
SCHEDULE_RELOAD = "homeassistant.config_entries.ConfigEntries.async_schedule_reload"


@pytest.fixture(autouse=True)
def _flow_only(hass: HomeAssistant):
    """Exercise only the config flow: skip frontend/http and the integration's own setup."""
    hass.config.components.update({"frontend", "http"})
    with (
        patch("custom_components.philips_airpurifier_coap.async_setup", return_value=True),
        patch("custom_components.philips_airpurifier_coap.async_unload_entry", return_value=True),
    ):
        yield


def _dhcp(ip: str, mac: str = MAC) -> DhcpServiceInfo:
    return DhcpServiceInfo(ip=ip, hostname="mxchip", macaddress=mac.replace(":", ""))


def _add_entry(
    hass: HomeAssistant,
    *,
    host: str = OLD_HOST,
    options: dict | None = None,
    with_device: bool = True,
    state: ConfigEntryState = ConfigEntryState.SETUP_RETRY,
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ID,
        title="HU1509 Living Room",
        data={
            CONF_HOST: host,
            CONF_MODEL: "HU1509",
            CONF_NAME: "Living Room",
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_STATUS: {},
        },
        options=options or {},
        state=state,
    )
    entry.add_to_hass(hass)
    if with_device:
        dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, DEVICE_ID)},
            connections={(dr.CONNECTION_NETWORK_MAC, MAC)},
        )
    return entry


async def _discover(hass: HomeAssistant, info: DhcpServiceInfo):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=info)


async def test_known_mac_on_new_ip_updates_host_without_probing(hass: HomeAssistant) -> None:
    """A configured device that moved to a new IP gets its host updated, no CoAP probe."""
    entry = _add_entry(hass)

    with (
        patch(CLIENT_CREATE, new=AsyncMock()) as create,
        patch(SCHEDULE_RELOAD) as reload,
    ):
        result = await _discover(hass, _dhcp(NEW_HOST))

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == NEW_HOST
    create.assert_not_called()
    reload.assert_called_once_with(entry.entry_id)


async def test_known_mac_on_same_ip_aborts_without_probing(hass: HomeAssistant) -> None:
    """Rediscovery at the current host must not probe: the probe steals the status observer."""
    entry = _add_entry(hass, host=NEW_HOST)

    with (
        patch(CLIENT_CREATE, new=AsyncMock()) as create,
        patch(SCHEDULE_RELOAD) as reload,
    ):
        result = await _discover(hass, _dhcp(NEW_HOST))

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == NEW_HOST
    create.assert_not_called()
    reload.assert_not_called()


async def test_host_override_in_options_is_updated(hass: HomeAssistant) -> None:
    """When the host lives in options (set via the options flow) that is what must change."""
    entry = _add_entry(hass, options={CONF_HOST: OLD_HOST})

    with patch(CLIENT_CREATE, new=AsyncMock()) as create, patch(SCHEDULE_RELOAD):
        result = await _discover(hass, _dhcp(NEW_HOST))

    assert result["reason"] == "already_configured"
    assert entry.options[CONF_HOST] == NEW_HOST
    create.assert_not_called()


async def test_loaded_entry_is_not_reloaded_twice(hass: HomeAssistant) -> None:
    """A loaded entry reloads through its update listener, so no extra reload is scheduled."""
    _add_entry(hass, state=ConfigEntryState.LOADED)

    with patch(CLIENT_CREATE, new=AsyncMock()), patch(SCHEDULE_RELOAD) as reload:
        await _discover(hass, _dhcp(NEW_HOST))

    reload.assert_not_called()


async def test_entry_without_mac_connection_matches_on_host(hass: HomeAssistant) -> None:
    """Entries whose MAC was never detected are still recognised by their host."""
    _add_entry(hass, host=NEW_HOST, with_device=False)

    with patch(CLIENT_CREATE, new=AsyncMock()) as create:
        result = await _discover(hass, _dhcp(NEW_HOST))

    assert result["reason"] == "already_configured"
    create.assert_not_called()


async def test_unknown_device_is_still_probed(hass: HomeAssistant) -> None:
    """Discovery of a device that is not configured keeps probing it over CoAP."""
    _add_entry(hass)

    with patch(CLIENT_CREATE, new=AsyncMock(side_effect=TimeoutError)) as create:
        await _discover(hass, _dhcp("192.168.2.200", mac="b0:f8:93:00:00:01"))

    create.assert_called_once_with("192.168.2.200")


async def test_other_device_on_stale_host_is_probed(hass: HomeAssistant) -> None:
    """A different device that inherited a configured entry's old IP is not mistaken for it."""
    entry = _add_entry(hass, host=OLD_HOST)

    with patch(CLIENT_CREATE, new=AsyncMock(side_effect=TimeoutError)) as create:
        await _discover(hass, _dhcp(OLD_HOST, mac="b0:f8:93:00:00:01"))

    create.assert_called_once_with(OLD_HOST)
    assert entry.data[CONF_HOST] == OLD_HOST


@pytest.mark.parametrize("state", [ConfigEntryState.SETUP_RETRY, ConfigEntryState.LOADED])
async def test_options_flow_reloads_entry_that_is_not_loaded(hass: HomeAssistant, state: ConfigEntryState) -> None:
    """Changing the host of an entry stuck in setup_retry must reload it right away."""
    entry = _add_entry(hass, state=state)
    client = AsyncMock()
    client.get_status.return_value = ({"DeviceId": DEVICE_ID}, 0)

    with (
        patch(CLIENT_CREATE, new=AsyncMock(return_value=client)),
        patch(SCHEDULE_RELOAD) as reload,
    ):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(flow["flow_id"], user_input={CONF_HOST: NEW_HOST})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_HOST] == NEW_HOST
    if state is ConfigEntryState.LOADED:
        reload.assert_not_called()
    else:
        reload.assert_called_once_with(entry.entry_id)
