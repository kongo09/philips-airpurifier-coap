"""Regression tests for Coordinator shutdown robustness.

Anything raised by Coordinator.shutdown() propagates out of
async_unload_entry, which makes Home Assistant mark the config entry
FAILED_UNLOAD. That state is terminal: reloading and re-enabling the entry are
both refused, so the device stays gone until Home Assistant is restarted.
Shutdown must therefore never raise, however broken the connection already is.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.philips_airpurifier_coap.coordinator import Coordinator

HOST = "10.0.0.1"


def _make_coordinator(client: MagicMock) -> Coordinator:
    """Build a Coordinator around a mocked CoAP client."""

    return Coordinator(MagicMock(), client, HOST, None)


async def test_shutdown_survives_already_shutdown_client() -> None:
    """Shutting a torn-down aiocoap context down twice must not raise.

    aiocoap clears its exchange bookkeeping on shutdown, so a second call
    raises "AttributeError: 'NoneType' object has no attribute 'values'".
    """

    client = MagicMock()
    client.shutdown = AsyncMock(side_effect=AttributeError("'NoneType' object has no attribute 'values'"))

    coordinator = _make_coordinator(client)

    await coordinator.shutdown()

    assert coordinator.client is None


async def test_shutdown_survives_timer_cancelled_mid_callback() -> None:
    """Timer.cancel() raises while its callback runs; shutdown must absorb it."""

    client = MagicMock()
    client.shutdown = AsyncMock()

    coordinator = _make_coordinator(client)
    coordinator._timer_disconnected._in_callback = True

    await coordinator.shutdown()

    assert coordinator.client is None


async def test_failed_reconnect_drops_the_dead_client() -> None:
    """A reconnect that cannot reach the device must not keep the old client.

    The client has already been shut down by then, so holding on to it is what
    makes the *next* shutdown() raise.
    """

    client = MagicMock()
    client.shutdown = AsyncMock()

    coordinator = _make_coordinator(client)

    with patch(
        "custom_components.philips_airpurifier_coap.coordinator.CoAPClient.create",
        side_effect=TimeoutError,
    ):
        await coordinator._reconnect()

    assert coordinator.client is None

    await coordinator.shutdown()


async def test_successful_reconnect_installs_the_new_client() -> None:
    """A reconnect that reaches the device must swap in the fresh client."""

    old_client = MagicMock()
    old_client.shutdown = AsyncMock()
    new_client = MagicMock()
    new_client.shutdown = AsyncMock()

    coordinator = _make_coordinator(old_client)

    with (
        patch(
            "custom_components.philips_airpurifier_coap.coordinator.CoAPClient.create",
            AsyncMock(return_value=new_client),
        ),
        patch.object(Coordinator, "_start_observing"),
    ):
        await coordinator._reconnect()

    assert coordinator.client is new_client

    await coordinator.shutdown()
