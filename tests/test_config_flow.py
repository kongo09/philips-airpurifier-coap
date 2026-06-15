"""Tests for the config and options flow."""

from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap import binary_sensor
from custom_components.philips_airpurifier_coap.const import (
    CONF_DEVICE_ID,
    CONF_FILTER_ALERT_THRESHOLD,
    CONF_MODEL,
    CONF_STATUS,
    DOMAIN,
    PhilipsApi,
)
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .fixtures.fake_client import FakeClient

AC3033_STATUS = {
    PhilipsApi.DEVICE_ID: "ABCD1234567890",
    PhilipsApi.WIFI_VERSION: "AWS_Philips_AIR@1.0.0",
    PhilipsApi.MODEL_ID: "AC3033/10",
    PhilipsApi.NAME: "Living Room",
}


def _patch_client(status: dict = AC3033_STATUS):
    """Patch the CoAP client used by the config flow."""
    client = AsyncMock()
    client.get_status = AsyncMock(return_value=(dict(status), 60))
    client.shutdown = AsyncMock()
    return patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(return_value=client),
    )


async def test_manual_flow_creates_entry(hass: HomeAssistant, bypass_integration_deps) -> None:
    """The manual flow resolves the model and creates an entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"

    with _patch_client():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MODEL] == "AC3033"
    assert result["result"].unique_id == "ABCD1234567890"


async def test_manual_flow_invalid_host(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An invalid host keeps the form open with an error."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "not a host!"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]


async def test_options_flow(hass: HomeAssistant, make_runtime, bypass_integration_deps) -> None:
    """The options flow stores the filter alert threshold."""
    entry, _ = make_runtime("AC3033")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FILTER_ALERT_THRESHOLD: 25}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_FILTER_ALERT_THRESHOLD] == 25


async def test_filter_alert_threshold_read_from_options(hass: HomeAssistant, make_runtime) -> None:
    """The filter alert sensor honours the configured threshold."""
    status = {
        PhilipsApi.DEVICE_ID: "ABCD1234567890",
        PhilipsApi.WIFI_VERSION: "AWS_Philips_AIR@1.0.0",
        PhilipsApi.FILTER_HEPA: 20,
        PhilipsApi.FILTER_HEPA_TOTAL: 100,
    }
    entry, _ = make_runtime("AC3033", status)
    hass.config_entries.async_update_entry(entry, options={CONF_FILTER_ALERT_THRESHOLD: 30})

    added: list = []
    await binary_sensor.async_setup_entry(hass, entry, lambda entities, *_: added.extend(entities))
    alert = next(e for e in added if isinstance(e, binary_sensor.PhilipsFilterAlertSensor))

    assert alert._threshold == 30
    # 20% is below the configured 30% threshold (but would be fine at the default 10%).
    assert alert.is_on is True


DISCOVERY_STATUS = {
    PhilipsApi.DEVICE_ID: "ABCD1234567890",
    PhilipsApi.WIFI_VERSION: "AWS_Philips_AIR@1.0.0",
    PhilipsApi.MODEL_ID: "AC3033/10",
    PhilipsApi.NAME: "Living Room",
}


def _existing_entry() -> MockConfigEntry:
    """Return a configured entry for the discovered device."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="ABCD1234567890",
        title="AC3033 Living Room",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_MODEL: "AC3033",
            CONF_NAME: "Living Room",
            CONF_DEVICE_ID: "ABCD1234567890",
            CONF_STATUS: DISCOVERY_STATUS,
        },
    )


def _patch_reload(status: dict = DISCOVERY_STATUS):
    """Patch everything needed for a flow that reloads the entry."""
    client = FakeClient(status)
    return [
        patch(
            "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
            AsyncMock(return_value=client),
        ),
        patch("custom_components.philips_airpurifier_coap.async_setup", return_value=True),
        patch(
            "custom_components.philips_airpurifier_coap.async_get_mac_address_from_host",
            AsyncMock(return_value=None),
        ),
    ]


async def test_dhcp_flow_creates_entry(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A DHCP discovery resolves the model and creates an entry after confirmation."""
    info = DhcpServiceInfo(ip="1.2.3.4", hostname="mxchip", macaddress="b0f893000000")
    with _patch_client(DISCOVERY_STATUS):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_DHCP}, data=info
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MODEL] == "AC3033"


async def test_dhcp_flow_timeout(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A DHCP host that times out aborts as an unsupported model."""
    info = DhcpServiceInfo(ip="1.2.3.4", hostname="mxchip", macaddress="b0f893000000")
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_DHCP}, data=info
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "model_unsupported"


async def test_dhcp_flow_connection_error(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A DHCP host that errors aborts with a timeout reason."""
    info = DhcpServiceInfo(ip="1.2.3.4", hostname="mxchip", macaddress="b0f893000000")
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(side_effect=OSError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_DHCP}, data=info
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "timeout"


async def test_ssdp_flow_no_host(hass: HomeAssistant, bypass_integration_deps) -> None:
    """SSDP discovery without an extractable host aborts."""
    info = SsdpServiceInfo(
        ssdp_usn="usn", ssdp_st="st", ssdp_location=None, upnp={}, ssdp_headers={}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=info
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_host"


async def test_ssdp_flow_timeout(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An SSDP host that times out aborts as an unsupported model."""
    info = SsdpServiceInfo(
        ssdp_usn="usn",
        ssdp_st="st",
        ssdp_location="http://1.2.3.4/",
        upnp={},
        ssdp_headers={"_host": "1.2.3.4"},
    )
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=info
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "model_unsupported"


async def test_dhcp_flow_unsupported_model(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An unsupported model aborts the DHCP flow."""
    status = {**DISCOVERY_STATUS, PhilipsApi.MODEL_ID: "ZZ9999/10"}
    info = DhcpServiceInfo(ip="1.2.3.4", hostname="mxchip", macaddress="b0f893000000")
    with _patch_client(status):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_DHCP}, data=info
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "model_unsupported"


async def test_ssdp_flow_creates_entry(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An SSDP discovery creates an entry after confirmation."""
    info = SsdpServiceInfo(
        ssdp_usn="usn",
        ssdp_st="urn:philips-com:device:DiProduct:1",
        ssdp_location="http://1.2.3.4/",
        upnp={},
        ssdp_headers={"_host": "1.2.3.4"},
    )
    with _patch_client(DISCOVERY_STATUS):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=info
        )
        assert result["type"] == FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_reauth_flow(hass: HomeAssistant, bypass_integration_deps) -> None:
    """The reauth flow updates the host and reloads the entry."""
    entry = _existing_entry()
    entry.add_to_hass(hass)
    create, setup, mac = _patch_reload()
    with create, setup, mac:
        result = await entry.start_reauth_flow(hass)
        assert result["type"] == FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.9"}
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_HOST] == "1.2.3.9"


async def test_reconfigure_flow(hass: HomeAssistant, bypass_integration_deps) -> None:
    """The reconfigure flow updates the host and reloads the entry."""
    entry = _existing_entry()
    entry.add_to_hass(hass)
    create, setup, mac = _patch_reload()
    with create, setup, mac:
        result = await entry.start_reconfigure_flow(hass)
        assert result["type"] == FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.8"}
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "1.2.3.8"


async def test_scan_flow_creates_entry(hass: HomeAssistant, bypass_integration_deps) -> None:
    """The scan flow discovers a device and creates an entry once picked."""
    devices = [
        {
            "ip": "1.2.3.4",
            "model": "AC3033/10",
            "name": "Living Room",
            "status": DISCOVERY_STATUS,
        }
    ]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.scan_for_devices",
        AsyncMock(return_value=devices),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "scan"}
        )
        await hass.async_block_till_done()
        if result["type"] == FlowResultType.SHOW_PROGRESS:
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pick_device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "1.2.3.4"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MODEL] == "AC3033"


async def test_scan_flow_no_devices(hass: HomeAssistant, bypass_integration_deps) -> None:
    """The scan flow aborts when nothing is found."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.scan_for_devices",
        AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "scan"}
        )
        await hass.async_block_till_done()
        if result["type"] == FlowResultType.SHOW_PROGRESS:
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_reauth_invalid_host(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An invalid host keeps the reauth form open with an error."""
    entry = _existing_entry()
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "not a host!"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]


async def test_reauth_timeout(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A timeout while reauthenticating keeps the form open with an error."""
    entry = _existing_entry()
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.9"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]


async def test_reauth_connection_error(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An unexpected error while reauthenticating keeps the form open."""
    entry = _existing_entry()
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(side_effect=OSError("boom")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.9"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]


async def test_reconfigure_timeout(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A timeout while reconfiguring keeps the form open with an error."""
    entry = _existing_entry()
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.8"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]


async def test_reconfigure_invalid_host(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An invalid host keeps the reconfigure form open with an error."""
    entry = _existing_entry()
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "not a host!"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]


async def test_reauth_different_device(hass: HomeAssistant, bypass_integration_deps) -> None:
    """Reauth against a different device aborts."""
    entry = _existing_entry()
    entry.add_to_hass(hass)
    other = {**DISCOVERY_STATUS, PhilipsApi.DEVICE_ID: "OTHERDEVICE0000"}
    with _patch_client(other):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.9"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_different_device"


async def test_reconfigure_different_device(hass: HomeAssistant, bypass_integration_deps) -> None:
    """Reconfigure against a different device aborts."""
    entry = _existing_entry()
    entry.add_to_hass(hass)
    other = {**DISCOVERY_STATUS, PhilipsApi.DEVICE_ID: "OTHERDEVICE0000"}
    with _patch_client(other):
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.8"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_different_device"
