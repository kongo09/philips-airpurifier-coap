"""Pytest configuration and fixtures for Philips AirPurifier CoAP tests."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.philips_airpurifier_coap.config_entry_data import ConfigEntryData
from custom_components.philips_airpurifier_coap.const import (
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_STATUS,
    DOMAIN,
)
from custom_components.philips_airpurifier_coap.coordinator import Coordinator
from custom_components.philips_airpurifier_coap.model import DeviceInformation
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from .fixtures.fake_client import FakeClient
from .fixtures.mock_data import SAMPLE_STATUS_AC3033


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom integration in every test."""
    yield


@pytest.fixture
def bypass_integration_deps(hass: HomeAssistant) -> None:
    """Treat the heavy manifest dependencies as already set up.

    The bare test environment cannot fully set up ``frontend``/``ssdp``;
    marking them as loaded lets the config and options flows initialise.
    """
    for dependency in ("http", "frontend", "ssdp"):
        hass.config.components.add(dependency)


@pytest.fixture
def make_runtime(
    hass: HomeAssistant,
) -> Callable[..., tuple[MockConfigEntry, ConfigEntryData]]:
    """Return a factory creating a config entry with initialized runtime data."""

    def _make(
        model: str = "AC3033",
        status: dict | None = None,
        device_id: str = "ABCD1234567890",
    ) -> tuple[MockConfigEntry, ConfigEntryData]:
        data_status = dict(status if status is not None else SAMPLE_STATUS_AC3033)

        entry = MockConfigEntry(
            domain=DOMAIN,
            title=f"{model} Living Room",
            unique_id=device_id,
            data={
                CONF_HOST: "192.168.1.100",
                CONF_MODEL: model,
                CONF_NAME: "Living Room",
                CONF_DEVICE_ID: device_id,
                CONF_STATUS: data_status,
            },
        )
        entry.add_to_hass(hass)

        client = FakeClient(data_status)
        coordinator = Coordinator(hass, client, "192.168.1.100", data_status, config_entry=entry)
        runtime = ConfigEntryData(
            device_information=DeviceInformation(
                model=model,
                name="Living Room",
                device_id=device_id,
                host="192.168.1.100",
            ),
            client=client,
            coordinator=coordinator,
            latest_status=data_status,
        )
        entry.runtime_data = runtime
        return entry, runtime

    return _make


@pytest.fixture
def setup_model(hass: HomeAssistant, bypass_integration_deps):
    """Return an async factory that fully sets up the integration for a model."""

    async def _setup(model: str, status: dict, *, with_status: bool = True):
        data = {
            CONF_HOST: "1.2.3.4",
            CONF_MODEL: model,
            CONF_NAME: "Living Room",
            CONF_DEVICE_ID: "ABCD1234567890",
        }
        if with_status:
            data[CONF_STATUS] = status
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="ABCD1234567890",
            title=f"{model} Living Room",
            data=data,
        )
        entry.add_to_hass(hass)
        client = FakeClient(status)
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
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        return entry, client

    return _setup
