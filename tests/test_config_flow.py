"""Tests for the Philips config flow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from custom_components.philips_airpurifier_coap.config_flow import (
    PhilipsAirPurifierConfigFlow,
    _async_get_status,
)


async def test_dhcp_skips_configured_host() -> None:
    """Do not open another observer for an already-configured host."""
    host = "192.0.2.1"
    entry = MagicMock(data={CONF_HOST: host}, options={})
    flow = PhilipsAirPurifierConfigFlow()

    with (
        patch.object(flow, "_async_current_entries", return_value=[entry]),
        patch(
            "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
            new_callable=AsyncMock,
        ) as create_client,
    ):
        result = await flow.async_step_dhcp(DhcpServiceInfo(ip=host, hostname="purifier", macaddress="001122334455"))

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    create_client.assert_not_awaited()


async def test_status_timeout_closes_temporary_client() -> None:
    """Close the temporary client when status observation times out."""
    status_cancelled = asyncio.Event()

    async def get_status():
        try:
            await asyncio.Event().wait()
        finally:
            status_cancelled.set()

    client = MagicMock()
    client.get_status = get_status
    client.shutdown = AsyncMock()
    timeout = MagicMock()
    timeout.async_timeout.side_effect = [asyncio.timeout(1), asyncio.timeout(0)]

    with (
        patch(
            "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
            new=AsyncMock(return_value=client),
        ),
        patch(
            "custom_components.philips_airpurifier_coap.config_flow.TimeoutManager",
            return_value=timeout,
        ),
        pytest.raises(TimeoutError),
    ):
        await _async_get_status("192.0.2.1")

    client.shutdown.assert_awaited_once()
    assert status_cancelled.is_set()
