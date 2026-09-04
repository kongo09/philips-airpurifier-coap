"""Tests for Philips status observation liveness."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.philips_airpurifier_coap.coordinator import Coordinator


async def test_stable_silence_refreshes_observer_without_reconnect() -> None:
    """Refresh Observe on the existing client when no status changes arrive."""
    observer_started = [asyncio.Event(), asyncio.Event()]
    observer_stops = 0

    async def observe_status():
        nonlocal observer_stops
        attempt = int(observer_started[0].is_set())
        observer_started[attempt].set()
        try:
            await asyncio.Event().wait()
            yield {}
        finally:
            observer_stops += 1

    client = MagicMock()
    client.observe_status = observe_status
    client.shutdown = AsyncMock()

    with patch("custom_components.philips_airpurifier_coap.coordinator.Timer") as timer_class:
        coordinator = Coordinator(MagicMock(), client, "192.0.2.1", {})
    refresh_observation = timer_class.call_args.kwargs["callback"]

    coordinator.async_add_listener(MagicMock())
    await observer_started[0].wait()

    await refresh_observation()
    await observer_started[1].wait()

    assert observer_stops == 1
    assert coordinator.client is client
    client.shutdown.assert_not_awaited()

    coordinator._task.cancel()
    await asyncio.gather(coordinator._task, return_exceptions=True)
