"""Tests for the Philips status coordinator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.philips_airpurifier_coap.coordinator import Coordinator


async def test_shutdown_waits_for_cancelled_observer() -> None:
    """Finish observation cancellation before closing the CoAP context."""
    observer_started = asyncio.Event()
    observer_stopped = asyncio.Event()

    async def observe_status():
        try:
            observer_started.set()
            await asyncio.Event().wait()
            yield {}
        finally:
            observer_stopped.set()

    async def shutdown_client() -> None:
        assert observer_stopped.is_set()

    client = MagicMock()
    client.observe_status = observe_status
    client.shutdown = AsyncMock(side_effect=shutdown_client)

    with patch("custom_components.philips_airpurifier_coap.coordinator.Timer"):
        coordinator = Coordinator(MagicMock(), client, "192.0.2.1", {})

    listener = MagicMock()
    coordinator.async_add_listener(listener)
    await observer_started.wait()
    coordinator.async_remove_listener(listener)

    await coordinator.shutdown()

    client.shutdown.assert_awaited_once()
