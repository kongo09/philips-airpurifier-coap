"""Exercise recovery without any real network or device writes."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.philips_airpurifier_coap import status_recovery
from custom_components.philips_airpurifier_coap.coordinator import Coordinator
from custom_components.philips_airpurifier_coap.status_recovery import BEEP, RecoveryError, StatusRecoveryClient


class Device:
    """Minimal CoAP peer reporting status after each accepted command."""

    def __init__(self, beep=100, *, immediate=False, reject=None, timeout=None):
        self.status = {BEEP: beep, "D03102": 0, "D0312F": 20, "D03105": 101}
        self.queue = asyncio.Queue()
        self.writes = []
        self.reject = reject
        self.timeout = timeout
        self.muted = asyncio.Event()
        self.closed = False
        if immediate:
            self.queue.put_nowait(dict(self.status))

    async def observe_status(self):
        """Wait for notifications until the subscription is cancelled."""
        while True:
            yield await self.queue.get()

    async def set_control_values(self, data, **kwargs):
        """Record exactly what would be sent over CoAP."""
        self.writes.append(dict(data))
        if len(self.writes) == self.reject:
            return False
        self.status.update(data)
        self.queue.put_nowait(dict(self.status))
        if data.get(BEEP) == 0:
            self.muted.set()
        if len(self.writes) == self.timeout:
            raise TimeoutError
        return True

    async def shutdown(self):
        """Record transport shutdown for lifecycle tests."""
        self.closed = True


@pytest.fixture(autouse=True)
def short_recovery_delays():
    """Use the same state machine with shorter deterministic waits."""
    with (
        patch.object(status_recovery, "WAKE_DELAY", 0.01),
        patch.object(status_recovery, "WAKE_SETTLE", 0.02),
        patch.object(status_recovery, "CONTROL_TIMEOUT", 0.1),
    ):
        yield


@pytest.mark.parametrize("beep", [0, 100])
async def test_silent_stream_restores_beep_without_touching_power_or_lights(beep):
    """Even a muted device can be woken with two off commands."""
    device = Device(beep)
    store = Mock()
    client = StatusRecoveryClient(device, store, beep)
    status, _ = await client.get_status()
    assert status == device.status
    assert status[BEEP] == beep
    assert device.writes == [{BEEP: 0}, {BEEP: beep}]
    assert status["D0312F"] == 20
    assert status["D03105"] == 101
    assert status["D03102"] == 0
    store.async_delay_save.assert_not_called()


async def test_normal_response_needs_no_recovery():
    """Do not send any command when the observation already works."""
    device = Device(immediate=True)
    client = StatusRecoveryClient(device, Mock(), 100)
    status, _ = await client.get_status()
    assert status[BEEP] == 100
    assert device.writes == []


async def test_unknown_beep_is_not_guessed():
    """An unknown previous setting must never be overwritten to recover status."""
    device = Device()
    client = StatusRecoveryClient(device, Mock(), None)
    iterator = client.observe_status()
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(anext(iterator), 0.05)
    await iterator.aclose()
    assert device.writes == []


@pytest.mark.parametrize("failure", ["wake_rejected", "restore_rejected", "wake_timeout"])
async def test_failed_recovery_is_not_reported_as_success(failure):
    """Attempt restoration even when a wake acknowledgement is rejected/lost."""
    device = Device(
        reject={"wake_rejected": 1, "restore_rejected": 2}.get(failure),
        timeout=1 if failure == "wake_timeout" else None,
    )
    store = Mock()
    client = StatusRecoveryClient(device, store, 100)
    with pytest.raises((RecoveryError, TimeoutError)):
        await client.get_status()
    assert device.writes == [{BEEP: 0}, {BEEP: 100}]
    store.async_delay_save.assert_not_called()


async def test_cancellation_waits_for_restore():
    """Cancelling observation during the temporary mute still restores beep."""
    device = Device()
    client = StatusRecoveryClient(device, Mock(), 100)
    task = asyncio.create_task(client.get_status())
    await device.muted.wait()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert device.status[BEEP] == 100
    assert device.writes == [{BEEP: 0}, {BEEP: 100}]


async def test_user_command_waits_for_recovery_then_wins():
    """An explicit user mute must not be undone by the recovery's restoration."""
    device = Device()
    store = Mock()
    client = StatusRecoveryClient(device, store, 100)
    reading = asyncio.create_task(client.get_status())
    await device.muted.wait()
    await client.set_control_value(BEEP, 0)
    await reading
    assert device.writes == [{BEEP: 0}, {BEEP: 100}, {BEEP: 0}]
    assert device.status[BEEP] == 0
    assert store.async_delay_save.call_args.args[0]() == {"beep": 0}


async def test_status_arriving_while_waiting_for_control_lock_skips_wake():
    """A queued nudge must recheck whether a normal notification has arrived."""
    device = Device()
    client = StatusRecoveryClient(device, Mock(), 100)
    async with client._lock:
        reading = asyncio.create_task(client.get_status())
        await asyncio.sleep(0.03)
        device.queue.put_nowait(dict(device.status))
        await asyncio.sleep(0)
    await reading
    assert device.writes == []


@pytest.mark.parametrize("success", [False, True])
async def test_only_successful_user_commands_change_saved_beep(success):
    """Do not learn an unacknowledged user setting."""
    device = Device(reject=None if success else 1)
    store = Mock()
    client = StatusRecoveryClient(device, store, 100)
    await client.set_control_value(BEEP, 0)
    assert bool(store.async_delay_save.call_count) is success


async def test_confirmed_status_and_reconnect_retain_latest_beep():
    """Remote/app changes become the resting setting for the next connection."""
    device = Device(0, immediate=True)
    store = Mock()
    client = StatusRecoveryClient(device, store, 100)
    await client.get_status()
    assert store.async_delay_save.call_args.args[0]() == {"beep": 0}
    replacement = Device(0)
    client = client.with_client(replacement)
    await client.get_status()
    assert replacement.writes == [{BEEP: 0}, {BEEP: 0}]


async def test_saved_beep_takes_priority_over_initial_entry_status(hass):
    """A restart must use the latest saved setting, not discovery-time status."""
    store = Mock(async_load=AsyncMock(return_value={"beep": 0}))
    device = Device(0)
    with patch.object(status_recovery, "Store", return_value=store):
        client = await StatusRecoveryClient.async_create(hass, device, "test-entry", {BEEP: 100})
    await client.get_status()
    assert device.writes == [{BEEP: 0}, {BEEP: 0}]


async def test_last_listener_removal_and_shutdown_wait_for_restore(hass):
    """Platform unloading must not cancel the restoration twice or close early."""
    device = Device()
    client = StatusRecoveryClient(device, Mock(), 100)
    coordinator = Coordinator(hass, client, "device.invalid", dict(device.status))
    remove = coordinator.async_add_listener(Mock())
    await device.muted.wait()
    remove()
    await coordinator.shutdown()
    assert device.closed
    assert device.writes == [{BEEP: 0}, {BEEP: 100}]
    assert device.status[BEEP] == 100


async def test_coordinator_reconnect_retains_recovery(hass):
    """Reconnect uses the wrapper and the latest beep state on a new transport."""
    old = Device(0, immediate=True)
    client = StatusRecoveryClient(old, Mock(), 100)
    await client.get_status()
    coordinator = Coordinator(hass, client, "device.invalid", dict(old.status))
    new = Device(0)
    updated = asyncio.Event()
    coordinator._listeners.append(updated.set)
    try:
        with patch(
            "custom_components.philips_airpurifier_coap.coordinator.CoAPClient.create",
            new=AsyncMock(return_value=new),
        ):
            await coordinator._reconnect()
        await asyncio.wait_for(updated.wait(), 1)
        assert old.closed
        assert isinstance(coordinator.client, StatusRecoveryClient)
        assert new.writes == [{BEEP: 0}, {BEEP: 0}]
    finally:
        await coordinator.shutdown()


@pytest.mark.parametrize("model, recovered", [("AMF870", True), ("AC3420", True), ("AC3421", False)])
async def test_entry_setup_scopes_recovery_by_model(hass, model, recovered):
    """Never enable device-setting recovery for untested device models."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.philips_airpurifier_coap import async_setup_entry
    from custom_components.philips_airpurifier_coap.const import DOMAIN

    device = Device()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "device.invalid",
            "model": model,
            "name": "Test",
            "device_id": "test-device",
            "status": dict(device.status),
        },
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.philips_airpurifier_coap.CoAPClient.create", return_value=device),
        patch("custom_components.philips_airpurifier_coap.async_get_mac_address_from_host", return_value=None),
        patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()),
    ):
        assert await async_setup_entry(hass, entry)
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    try:
        assert isinstance(coordinator.client, StatusRecoveryClient) is recovered
    finally:
        await coordinator.shutdown()
