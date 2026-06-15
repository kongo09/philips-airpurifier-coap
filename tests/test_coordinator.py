"""Tests for the push DataUpdateCoordinator."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.philips_airpurifier_coap.coordinator import (
    MISSED_PACKAGE_COUNT,
    Coordinator,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util


class FakeClient:
    """Minimal stand-in for ``aioairctrl.CoAPClient``."""

    def __init__(self, status: dict, timeout: int = 60) -> None:
        """Initialize the fake client."""
        self.initial_status = status
        self.timeout = timeout
        self.queue: asyncio.Queue[dict] = asyncio.Queue()
        self.shutdown = AsyncMock()
        self.set_control_value = AsyncMock()
        self.set_control_values = AsyncMock()

    async def get_status(self) -> tuple[dict, int]:
        """Return a copy of the initial status and the reporting interval."""
        return dict(self.initial_status), self.timeout

    async def observe_status(self):
        """Yield every status pushed onto the queue (a live stream)."""
        while True:
            yield await self.queue.get()


def _make_coordinator(hass: HomeAssistant, client: FakeClient, status: dict | None):
    """Create a coordinator instance for tests."""
    return Coordinator(hass, client, "1.2.3.4", status)


async def test_is_data_update_coordinator(hass: HomeAssistant) -> None:
    """The coordinator must be a proper DataUpdateCoordinator."""
    coord = _make_coordinator(hass, FakeClient({"pwr": "1"}), {"pwr": "1"})
    assert isinstance(coord, DataUpdateCoordinator)
    assert coord.status == {"pwr": "1"}


async def test_first_refresh_sets_data_and_timeout(hass: HomeAssistant) -> None:
    """async_first_refresh should populate data and learn the interval."""
    client = FakeClient({"pwr": "1"}, timeout=30)
    coord = _make_coordinator(hass, client, None)

    await coord.async_first_refresh()

    assert coord.data == {"pwr": "1"}
    assert coord.status == {"pwr": "1"}
    assert coord._timeout == 30


async def test_first_refresh_failure_raises_not_ready(hass: HomeAssistant) -> None:
    """A failing first refresh must raise ConfigEntryNotReady."""
    client = FakeClient({})
    client.get_status = AsyncMock(side_effect=OSError("boom"))
    coord = _make_coordinator(hass, client, None)

    with pytest.raises(ConfigEntryNotReady):
        await coord.async_first_refresh()


async def test_push_update_propagates(hass: HomeAssistant) -> None:
    """A pushed status update should reach the listeners via the coordinator."""
    client = FakeClient({"pwr": "1"})
    coord = _make_coordinator(hass, client, {"pwr": "1"})

    updates: list[dict] = []

    @callback
    def _listener() -> None:
        updates.append(dict(coord.data))

    remove = coord.async_add_listener(_listener)
    await hass.async_block_till_done()

    await client.queue.put({"pwr": "0", "pm25": 12})
    await hass.async_block_till_done()

    assert coord.data == {"pwr": "0", "pm25": 12}
    assert coord.last_update_success
    assert {"pwr": "0", "pm25": 12} in updates

    remove()
    await coord.async_shutdown()


async def test_observing_stops_without_listeners(hass: HomeAssistant) -> None:
    """Removing the last listener should stop the observation task."""
    client = FakeClient({"pwr": "1"})
    coord = _make_coordinator(hass, client, {"pwr": "1"})

    remove = coord.async_add_listener(lambda: None)
    await hass.async_block_till_done()
    assert coord._observe_task is not None

    remove()
    assert coord._observe_task is None

    await coord.async_shutdown()


async def test_watchdog_triggers_reconnect(hass: HomeAssistant) -> None:
    """When no update arrives in time, the watchdog reconnects the client."""
    client = FakeClient({"pwr": "1"}, timeout=1)
    coord = _make_coordinator(hass, client, None)
    await coord.async_first_refresh()  # learns the 1s reporting interval
    new_client = FakeClient({"pwr": "1"}, timeout=1)

    coord.async_add_listener(lambda: None)
    await hass.async_block_till_done()

    with patch(
        "custom_components.philips_airpurifier_coap.coordinator.CoAPClient.create",
        AsyncMock(return_value=new_client),
    ) as mock_create:
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=MISSED_PACKAGE_COUNT + 2)
        )
        await hass.async_block_till_done()
        mock_create.assert_awaited_once()

    assert coord.client is new_client
    client.shutdown.assert_awaited()

    await coord.async_shutdown()


async def test_reconnect_failure_marks_unavailable(hass: HomeAssistant) -> None:
    """A failed reconnect marks the coordinator as unavailable and retries."""
    client = FakeClient({"pwr": "1"}, timeout=1)
    coord = _make_coordinator(hass, client, None)
    await coord.async_first_refresh()
    coord.async_add_listener(lambda: None)
    await hass.async_block_till_done()

    with patch(
        "custom_components.philips_airpurifier_coap.coordinator.CoAPClient.create",
        AsyncMock(side_effect=OSError("boom")),
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=MISSED_PACKAGE_COUNT + 2)
        )
        await hass.async_block_till_done()

    assert coord.last_update_success is False

    await coord.async_shutdown()


async def test_shutdown_cancels_and_closes(hass: HomeAssistant) -> None:
    """async_shutdown must stop the tasks and close the client."""
    client = FakeClient({"pwr": "1"})
    coord = _make_coordinator(hass, client, {"pwr": "1"})

    coord.async_add_listener(lambda: None)
    await hass.async_block_till_done()

    await coord.async_shutdown()

    assert coord._observe_task is None
    client.shutdown.assert_awaited()
