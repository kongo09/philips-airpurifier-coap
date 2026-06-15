"""Targeted tests closing the remaining coverage gaps across the integration.

These exercise the error branches, rarely-hit properties and lifecycle corners
that the behavioural suites do not reach, to keep coverage at the Platinum bar.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.philips_airpurifier_coap import (
    binary_sensor,
    climate,
    helpers,
    humidifier,
    light,
    number,
    select,
    sensor,
    switch,
)
from custom_components.philips_airpurifier_coap.const import (
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_STATUS,
    DOMAIN,
    FanFunction,
    PhilipsApi,
    PresetMode,
)
from custom_components.philips_airpurifier_coap.coordinator import Coordinator
from homeassistant.components.climate import SWING_OFF, SWING_ON, HVACMode
from homeassistant.components.light import EFFECT_OFF
from homeassistant.config_entries import (
    SOURCE_SSDP,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .fixtures.fake_client import FakeClient

_BASE = {
    PhilipsApi.DEVICE_ID: "ABCD1234567890",
    PhilipsApi.WIFI_VERSION: "AWS_Philips_AIR@1.0.0",
}


def _build(cls, hass, make_runtime, status, *args, model="AC3033", stub_write=False):
    """Construct an entity directly with a controlled status."""
    entry, runtime = make_runtime(model=model, status={**_BASE, **status})
    entity = cls(hass, entry, runtime, *args)
    if stub_write:
        entity.async_write_ha_state = lambda: None
    return entity, runtime


def _desc(types, key):
    """Return the entity description with the given key from a description tuple."""
    return next(d for d in types if d.key == key)


# --------------------------------------------------------------------------- #
# __init__.py
# --------------------------------------------------------------------------- #
def _make_entry(model="AC3033", status=None, with_status=True):
    """Build a MockConfigEntry for the given model."""
    full = {
        **_BASE,
        PhilipsApi.MODEL_ID: "AC3033/10",
        PhilipsApi.NAME: "Living Room",
        PhilipsApi.POWER: "1",
    }
    data = {
        CONF_HOST: "1.2.3.4",
        CONF_MODEL: model,
        CONF_NAME: "Living Room",
        CONF_DEVICE_ID: "ABCD1234567890",
    }
    if with_status:
        data[CONF_STATUS] = status or full
    return MockConfigEntry(
        domain=DOMAIN, unique_id="ABCD1234567890", title=f"{model} Living Room", data=data
    )


def _setup_patches(client, mac=None):
    """Return the patch context managers needed to set the integration up."""
    return [
        patch(
            "custom_components.philips_airpurifier_coap.CoAPClient.create",
            AsyncMock(return_value=client),
        ),
        patch("custom_components.philips_airpurifier_coap.async_setup", return_value=True),
        patch(
            "custom_components.philips_airpurifier_coap.async_get_mac_address_from_host",
            AsyncMock(return_value=mac),
        ),
    ]


async def test_listing_view_get(hass: HomeAssistant) -> None:
    """The async get() handler returns the icon list via the executor."""
    import json
    import os

    from custom_components.philips_airpurifier_coap import ListingView, __file__ as init_file

    iconpath = os.path.join(os.path.dirname(init_file), "icons", "pap")
    view = ListingView("/url", iconpath, hass)
    icons = json.loads(await view.get(None))
    assert isinstance(icons, list)


async def test_async_get_mac_ipv6(hass: HomeAssistant) -> None:
    """An IPv6 host is resolved through the ip6 code path."""
    from custom_components.philips_airpurifier_coap import async_get_mac_address_from_host

    with patch(
        "custom_components.philips_airpurifier_coap.get_mac_address",
        return_value="AA:BB:CC:DD:EE:FF",
    ):
        mac = await async_get_mac_address_from_host(hass, "fe80::1")
    assert mac == "aa:bb:cc:dd:ee:ff"


async def test_setup_generic_connection_error(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A non-timeout connection failure also yields a retry."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.philips_airpurifier_coap.CoAPClient.create",
            AsyncMock(side_effect=OSError("boom")),
        ),
        patch("custom_components.philips_airpurifier_coap.async_setup", return_value=True),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_deferred_mac_failure_is_swallowed(
    hass: HomeAssistant, bypass_integration_deps
) -> None:
    """A failing background MAC lookup must not break setup."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    client = FakeClient(entry.data[CONF_STATUS])
    create, setup, _ = _setup_patches(client)
    with (
        create,
        setup,
        patch(
            "custom_components.philips_airpurifier_coap.async_get_mac_address_from_host",
            AsyncMock(side_effect=OSError("no mac")),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.device_information.mac is None


async def test_setup_first_refresh_timeout(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A timeout while fetching the missing status yields a retry."""
    entry = _make_entry(with_status=False)
    entry.add_to_hass(hass)
    client = FakeClient({})
    create, setup, mac = _setup_patches(client)
    with (
        create,
        setup,
        mac,
        patch.object(Coordinator, "async_first_refresh", AsyncMock(side_effect=TimeoutError)),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_options_update_reloads_entry(hass: HomeAssistant, bypass_integration_deps) -> None:
    """Updating the options triggers the reload listener."""
    from custom_components.philips_airpurifier_coap.const import CONF_FILTER_ALERT_THRESHOLD

    entry = _make_entry()
    entry.add_to_hass(hass)
    client = FakeClient(entry.data[CONF_STATUS])
    create, setup, mac = _setup_patches(client)
    with create, setup, mac:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with patch(
            "custom_components.philips_airpurifier_coap.async_unload_entry",
            wraps=__import__(
                "custom_components.philips_airpurifier_coap", fromlist=["async_unload_entry"]
            ).async_unload_entry,
        ) as unload:
            hass.config_entries.async_update_entry(entry, options={CONF_FILTER_ALERT_THRESHOLD: 22})
            await hass.async_block_till_done()
        assert unload.called


async def test_unload_when_platforms_fail(hass: HomeAssistant, bypass_integration_deps) -> None:
    """If platform unload fails, the coordinator is left running."""
    from custom_components.philips_airpurifier_coap import async_unload_entry

    entry = _make_entry()
    entry.add_to_hass(hass)
    client = FakeClient(entry.data[CONF_STATUS])
    create, setup, mac = _setup_patches(client)
    with create, setup, mac:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with patch.object(
            hass.config_entries, "async_unload_platforms", AsyncMock(return_value=False)
        ):
            assert await async_unload_entry(hass, entry) is False
    # The coordinator was not shut down because unload failed.
    client.shutdown.assert_not_awaited()
    await entry.runtime_data.coordinator.async_shutdown()


# --------------------------------------------------------------------------- #
# helpers.py
# --------------------------------------------------------------------------- #
def test_get_active_ips_arp_read_error() -> None:
    """A failure reading the ARP table yields an empty list."""
    with patch("builtins.open", side_effect=OSError("nope")):
        assert helpers.get_active_ips_from_arp() == []


async def test_ping_sweep_handles_send_error() -> None:
    """A socket send error during the sweep is ignored."""
    sock = MagicMock()
    sock.sendto.side_effect = OSError("unreachable")
    with (
        patch("socket.socket", return_value=sock),
        patch(
            "custom_components.philips_airpurifier_coap.helpers.asyncio.sleep",
            AsyncMock(),
        ),
    ):
        await helpers.ping_sweep("192.168.1")


async def test_check_single_ip_empty_status() -> None:
    """An empty status (no device) returns None."""
    client = AsyncMock()
    client.get_status = AsyncMock(return_value=({}, 60))
    client.shutdown = AsyncMock()
    with patch(
        "custom_components.philips_airpurifier_coap.helpers.CoAPClient.create",
        AsyncMock(return_value=client),
    ):
        result = await helpers._check_single_ip("1.2.3.4", asyncio.Semaphore(1), 1.0)
    assert result is None


async def test_check_single_ip_cancelled() -> None:
    """A cancellation while probing is handled gracefully."""
    client = AsyncMock()
    client.get_status = AsyncMock(side_effect=asyncio.CancelledError)
    client.shutdown = AsyncMock()
    with patch(
        "custom_components.philips_airpurifier_coap.helpers.CoAPClient.create",
        AsyncMock(return_value=client),
    ):
        result = await helpers._check_single_ip("1.2.3.4", asyncio.Semaphore(1), 1.0)
    assert result is None


async def test_check_single_ip_generic_error() -> None:
    """An unexpected error while probing yields None."""
    client = AsyncMock()
    client.get_status = AsyncMock(side_effect=ValueError("weird"))
    client.shutdown = AsyncMock()
    with patch(
        "custom_components.philips_airpurifier_coap.helpers.CoAPClient.create",
        AsyncMock(return_value=client),
    ):
        result = await helpers._check_single_ip("1.2.3.4", asyncio.Semaphore(1), 1.0)
    assert result is None


async def test_check_single_ip_shutdown_error() -> None:
    """A failing shutdown does not mask a successful discovery."""
    client = AsyncMock()
    client.get_status = AsyncMock(
        return_value=({PhilipsApi.MODEL_ID: "AC3033/10", PhilipsApi.DEVICE_ID: "x"}, 60)
    )
    client.shutdown = AsyncMock(side_effect=OSError("cannot close"))
    with patch(
        "custom_components.philips_airpurifier_coap.helpers.CoAPClient.create",
        AsyncMock(return_value=client),
    ):
        result = await helpers._check_single_ip("1.2.3.4", asyncio.Semaphore(1), 1.0)
    assert result["model"] == "AC3033/10"


async def test_scan_falls_back_when_arp_empty() -> None:
    """With no ARP entries, the scan falls back to the common DHCP range."""
    device = {"ip": "192.168.1.5", "model": "AC3033/10", "name": "x", "status": {}}

    async def _check(ip, *_):
        return device if ip == "192.168.1.5" else None

    with (
        patch.object(helpers, "get_local_ip", return_value="192.168.1.10"),
        patch.object(helpers, "ping_sweep", AsyncMock()),
        patch.object(helpers, "get_active_ips_from_arp", return_value=[]),
        patch.object(helpers, "_check_single_ip", side_effect=_check),
    ):
        devices = await helpers.scan_for_devices(timeout=0.01)
    assert device in devices


# --------------------------------------------------------------------------- #
# coordinator.py
# --------------------------------------------------------------------------- #
async def test_stop_observing_without_task(hass: HomeAssistant) -> None:
    """Stopping observation with no running task is a no-op."""
    coord = Coordinator(hass, FakeClient({"pwr": "1"}), "1.2.3.4", {"pwr": "1"})
    coord._stop_observing()  # no observe task armed
    assert coord._observe_task is None


async def test_observe_stream_ends(hass: HomeAssistant) -> None:
    """An observation stream that ends without data simply stops."""

    class _EmptyClient(FakeClient):
        async def observe_status(self):
            return
            yield  # pragma: no cover - makes this an async generator

    coord = Coordinator(hass, _EmptyClient({"pwr": "1"}), "1.2.3.4", {"pwr": "1"})
    coord.async_add_listener(lambda: None)
    await hass.async_block_till_done()
    await coord.async_shutdown()


async def test_observe_stream_error_marks_unavailable(hass: HomeAssistant) -> None:
    """An error in the observation stream marks the coordinator unavailable."""

    class _FailingClient(FakeClient):
        async def observe_status(self):
            raise ValueError("stream dead")
            yield  # pragma: no cover - makes this an async generator

    coord = Coordinator(hass, _FailingClient({"pwr": "1"}), "1.2.3.4", {"pwr": "1"})
    coord.async_add_listener(lambda: None)
    await hass.async_block_till_done()
    assert coord.last_update_success is False
    await coord.async_shutdown()


async def test_watchdog_cancels_pending_reconnect(hass: HomeAssistant) -> None:
    """A new watchdog timeout cancels an in-flight reconnect task."""
    coord = Coordinator(hass, FakeClient({"pwr": "1"}), "1.2.3.4", {"pwr": "1"})

    async def _sleep_forever():
        await asyncio.sleep(3600)

    coord._reconnect_task = hass.async_create_task(_sleep_forever())
    with patch(
        "custom_components.philips_airpurifier_coap.coordinator.CoAPClient.create",
        AsyncMock(return_value=FakeClient({"pwr": "1"})),
    ):
        coord._handle_watchdog_timeout(None)
        await hass.async_block_till_done()
    await coord.async_shutdown()


async def test_reconnect_propagates_cancellation(hass: HomeAssistant) -> None:
    """Cancellation during a reconnect is re-raised, not swallowed."""
    coord = Coordinator(hass, FakeClient({"pwr": "1"}), "1.2.3.4", {"pwr": "1"})
    with (
        patch(
            "custom_components.philips_airpurifier_coap.coordinator.CoAPClient.create",
            AsyncMock(side_effect=asyncio.CancelledError),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await coord._async_reconnect()
    await coord.async_shutdown()


# --------------------------------------------------------------------------- #
# binary_sensor.py
# --------------------------------------------------------------------------- #
async def test_binary_sensor_unknown_model(hass: HomeAssistant, make_runtime) -> None:
    """An unknown model only yields the filter-alert sensor, never plain ones."""
    entry, runtime = make_runtime(
        model="AC3033",
        status={**_BASE, PhilipsApi.FILTER_HEPA: 50, PhilipsApi.FILTER_HEPA_TOTAL: 100},
    )
    runtime.device_information.model = "UNKNOWN9999"
    added: list = []
    await binary_sensor.async_setup_entry(hass, entry, lambda e, *_: added.extend(e))
    assert all(isinstance(e, binary_sensor.PhilipsFilterAlertSensor) for e in added)


async def test_binary_sensor_is_on_variants(hass: HomeAssistant, make_runtime) -> None:
    """is_on returns None when the key is absent and bool(value) without a value_fn."""
    desc_none = binary_sensor.PhilipsBinarySensorEntityDescription(
        key="zzz_absent", translation_key="x", value_fn=None
    )
    ent, _ = _build(binary_sensor.PhilipsBinarySensor, hass, make_runtime, {}, desc_none)
    assert ent.is_on is None  # key absent -> unknown

    desc_plain = binary_sensor.PhilipsBinarySensorEntityDescription(
        key="plainkey", translation_key="x", value_fn=None
    )
    ent2, _ = _build(
        binary_sensor.PhilipsBinarySensor, hass, make_runtime, {"plainkey": 1}, desc_plain
    )
    assert ent2.is_on is True  # bool(value) path, no value_fn


async def test_filter_alert_low_filter_attributes(hass: HomeAssistant, make_runtime) -> None:
    """The alert sensor reports per-filter percentages for low filters."""
    status = {PhilipsApi.FILTER_HEPA: 5, PhilipsApi.FILTER_HEPA_TOTAL: 100}
    ent, _ = _build(
        binary_sensor.PhilipsFilterAlertSensor,
        hass,
        make_runtime,
        status,
        [PhilipsApi.FILTER_HEPA],
    )
    attrs = ent.extra_state_attributes
    assert PhilipsApi.FILTER_HEPA in ent._get_low_filters()
    assert any(k.endswith("_percentage") for k in attrs)


async def test_filter_alert_get_low_filters_branches(hass: HomeAssistant, make_runtime) -> None:
    """_get_low_filters skips absent keys, unknown keys, and zero totals."""
    # Key in the list but absent from the status -> skipped.
    ent_absent, _ = _build(
        binary_sensor.PhilipsFilterAlertSensor, hass, make_runtime, {}, [PhilipsApi.FILTER_HEPA]
    )
    assert ent_absent._get_low_filters() == {}

    # Key present but unknown to the filter catalogue -> skipped.
    ent_unknown, _ = _build(
        binary_sensor.PhilipsFilterAlertSensor,
        hass,
        make_runtime,
        {"fakefilter": 5},
        ["fakefilter"],
    )
    assert ent_unknown._get_low_filters() == {}

    # Total present but zero -> no percentage computed.
    ent_zero, _ = _build(
        binary_sensor.PhilipsFilterAlertSensor,
        hass,
        make_runtime,
        {PhilipsApi.FILTER_HEPA: 5, PhilipsApi.FILTER_HEPA_TOTAL: 0},
        [PhilipsApi.FILTER_HEPA],
    )
    assert ent_zero._get_low_filters() == {}

    # No total available -> raw hours value used when below ~3 days.
    ent_hours, _ = _build(
        binary_sensor.PhilipsFilterAlertSensor,
        hass,
        make_runtime,
        {PhilipsApi.FILTER_PRE: 50},
        [PhilipsApi.FILTER_PRE],
    )
    assert ent_hours._get_low_filters() == {PhilipsApi.FILTER_PRE: 50}


async def test_filter_alert_fires_event(hass: HomeAssistant, make_runtime) -> None:
    """A filter dropping below the threshold fires the filter-alert event once."""
    status = {PhilipsApi.FILTER_HEPA: 80, PhilipsApi.FILTER_HEPA_TOTAL: 100}
    ent, runtime = _build(
        binary_sensor.PhilipsFilterAlertSensor,
        hass,
        make_runtime,
        status,
        [PhilipsApi.FILTER_HEPA],
        stub_write=True,
    )
    events = async_capture_events(hass, binary_sensor.EVENT_FILTER_ALERT)

    # First update establishes the baseline (filter healthy -> no event).
    ent._handle_coordinator_update()
    await hass.async_block_till_done()
    assert not events

    # Drop the filter below the default threshold -> a single alert fires.
    runtime.coordinator.data = {
        **_BASE,
        PhilipsApi.FILTER_HEPA: 5,
        PhilipsApi.FILTER_HEPA_TOTAL: 100,
    }
    ent._handle_coordinator_update()
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["filter_key"] == PhilipsApi.FILTER_HEPA
    assert events[0].data["percentage"] == 5


# --------------------------------------------------------------------------- #
# sensor.py
# --------------------------------------------------------------------------- #
def test_icon_from_map_non_numeric() -> None:
    """A non-numeric value falls back to the first icon in the map."""
    icon_map = ((0, "mdi:a"), (10, "mdi:b"))
    assert sensor._icon_from_map("not-a-number", icon_map) == "mdi:a"
    assert sensor._icon_from_map(5, None) is None


async def test_sensor_unknown_model_still_builds(hass: HomeAssistant, make_runtime) -> None:
    """Sensors are still created for an unknown model (no unavailable lists)."""
    entry, runtime = make_runtime(model="AC3033", status={**_BASE, PhilipsApi.PM25: 12})
    runtime.device_information.model = "UNKNOWN9999"
    added: list = []
    await sensor.async_setup_entry(hass, entry, lambda e, *_: added.extend(e))
    assert any(e.entity_description.key == PhilipsApi.PM25 for e in added)


async def test_sensor_native_value_none(hass: HomeAssistant, make_runtime) -> None:
    """A sensor whose key is absent reports no value."""
    desc = _desc(sensor.SENSOR_TYPES, PhilipsApi.PM25)
    ent, _ = _build(sensor.PhilipsSensor, hass, make_runtime, {}, desc)
    assert ent.native_value is None


async def test_filter_sensor_without_total(hass: HomeAssistant, make_runtime) -> None:
    """A filter without a total reports remaining hours and no extra total attrs."""
    desc = _desc(sensor.FILTER_TYPES, PhilipsApi.FILTER_PRE)
    ent, _ = _build(
        sensor.PhilipsFilterSensor, hass, make_runtime, {PhilipsApi.FILTER_PRE: 100}, desc
    )
    from homeassistant.const import UnitOfTime

    assert ent._attr_native_unit_of_measurement == UnitOfTime.HOURS
    assert ent.native_value == "100"
    assert ent.extra_state_attributes == {}


# --------------------------------------------------------------------------- #
# switch.py / select.py / number.py
# --------------------------------------------------------------------------- #
async def test_switch_unknown_model(hass: HomeAssistant, make_runtime) -> None:
    """An unknown model creates no switches."""
    entry, runtime = make_runtime(model="AC3033")
    runtime.device_information.model = "UNKNOWN9999"
    added: list = []
    await switch.async_setup_entry(hass, entry, lambda e, *_: added.extend(e))
    assert added == []


async def test_switch_turn_off(hass: HomeAssistant, make_runtime) -> None:
    """Turning a switch off sends the configured off value."""
    desc = _desc(switch.SWITCH_TYPES, PhilipsApi.CHILD_LOCK)
    ent, runtime = _build(
        switch.PhilipsSwitch,
        hass,
        make_runtime,
        {PhilipsApi.CHILD_LOCK: True},
        desc,
        stub_write=True,
    )
    await ent.async_turn_off()
    runtime.client.set_control_value.assert_awaited_with(PhilipsApi.CHILD_LOCK, False)


async def test_select_unknown_model(hass: HomeAssistant, make_runtime) -> None:
    """An unknown model creates no selects."""
    entry, runtime = make_runtime(model="AC3033")
    runtime.device_information.model = "UNKNOWN9999"
    added: list = []
    await select.async_setup_entry(hass, entry, lambda e, *_: added.extend(e))
    assert added == []


async def test_select_invalid_option(hass: HomeAssistant, make_runtime) -> None:
    """Selecting an unknown option is ignored without a client call."""
    desc = _desc(select.SELECT_TYPES, PhilipsApi.FUNCTION)
    ent, runtime = _build(select.PhilipsSelect, hass, make_runtime, {}, desc, stub_write=True)
    await ent.async_select_option("definitely-not-an-option")
    runtime.client.set_control_value.assert_not_awaited()


async def test_number_unknown_model(hass: HomeAssistant, make_runtime) -> None:
    """An unknown model creates no numbers."""
    entry, runtime = make_runtime(model="AC3033")
    runtime.device_information.model = "UNKNOWN9999"
    added: list = []
    await number.async_setup_entry(hass, entry, lambda e, *_: added.extend(e))
    assert added == []


async def test_number_set_value_snaps_to_boundaries(hass: HomeAssistant, make_runtime) -> None:
    """Setting a value below the minimum or off-step snaps it into range."""
    desc = _desc(number.NUMBER_TYPES, PhilipsApi.NEW2_OSCILLATION)
    ent, runtime = _build(number.PhilipsNumber, hass, make_runtime, {}, desc, stub_write=True)

    await ent.async_set_native_value(-10)  # below native_min_value -> clamped to 0
    runtime.client.set_control_value.assert_awaited_with(PhilipsApi.NEW2_OSCILLATION, 0)

    await ent.async_set_native_value(33)  # off-step (step 5) -> snapped to 30
    runtime.client.set_control_value.assert_awaited_with(PhilipsApi.NEW2_OSCILLATION, 30)


# --------------------------------------------------------------------------- #
# light.py
# --------------------------------------------------------------------------- #
async def test_light_unknown_model(hass: HomeAssistant, make_runtime) -> None:
    """An unknown model creates no lights."""
    entry, runtime = make_runtime(model="AC3033")
    runtime.device_information.model = "UNKNOWN9999"
    added: list = []
    await light.async_setup_entry(hass, entry, lambda e, *_: added.extend(e))
    assert added == []


async def test_light_brightness_non_dimmable(hass: HomeAssistant, make_runtime) -> None:
    """A non-dimmable light has no brightness."""
    desc = _desc(light.LIGHT_TYPES, PhilipsApi.DISPLAY_BACKLIGHT)
    ent, _ = _build(
        light.PhilipsLight, hass, make_runtime, {PhilipsApi.DISPLAY_BACKLIGHT: "1"}, desc
    )
    assert ent.brightness is None


async def test_light_brightness_missing_value(hass: HomeAssistant, make_runtime) -> None:
    """A dimmable light with no stored value has no brightness."""
    desc = _desc(light.LIGHT_TYPES, PhilipsApi.LIGHT_BRIGHTNESS)
    ent, _ = _build(light.PhilipsLight, hass, make_runtime, {}, desc)
    assert ent.brightness is None


async def test_light_turn_on_variants(hass: HomeAssistant, make_runtime) -> None:
    """Turn-on covers the non-auto effect, non-dimmable and medium branches."""
    # Non-auto effect on a light that supports the auto effect.
    desc_auto = _desc(light.LIGHT_TYPES, PhilipsApi.NEW2_DISPLAY_BACKLIGHT3)
    ent_auto, runtime = _build(
        light.PhilipsLight, hass, make_runtime, {}, desc_auto, stub_write=True
    )
    await ent_auto.async_turn_on(effect=EFFECT_OFF)
    runtime.client.set_control_value.assert_awaited()

    # Medium branch: a brightness below full snaps to the medium value.
    await ent_auto.async_turn_on(brightness=100)
    runtime.client.set_control_value.assert_awaited_with(ent_auto._key, desc_auto.medium_value)

    # Non-dimmable turn-on with no kwargs.
    desc_plain = _desc(light.LIGHT_TYPES, PhilipsApi.DISPLAY_BACKLIGHT)
    ent_plain, runtime2 = _build(
        light.PhilipsLight, hass, make_runtime, {}, desc_plain, stub_write=True
    )
    await ent_plain.async_turn_on()
    runtime2.client.set_control_value.assert_awaited_with(ent_plain._key, desc_plain.on_value)


# --------------------------------------------------------------------------- #
# climate.py
# --------------------------------------------------------------------------- #
def _heater(hass, make_runtime, status, presets, oscillation=None, stub_write=False):
    """Construct a PhilipsHeater with controlled presets and oscillation."""
    desc = climate.HEATER_TYPES[0]
    return _build(
        climate.PhilipsHeater,
        hass,
        make_runtime,
        status,
        desc,
        presets,
        oscillation or {},
        model="CX5120",
        stub_write=stub_write,
    )


async def test_climate_unknown_model(hass: HomeAssistant, make_runtime) -> None:
    """An unknown model creates no heater."""
    entry, runtime = make_runtime(model="CX5120")
    runtime.device_information.model = "UNKNOWN9999"
    added: list = []
    await climate.async_setup_entry(hass, entry, lambda e, *_: added.extend(e))
    assert added == []


async def test_climate_hvac_modes(hass: HomeAssistant, make_runtime) -> None:
    """hvac_mode maps the power/preset state onto the HVAC modes."""
    on = {PhilipsApi.NEW2_POWER: 1}

    auto, _ = _heater(hass, make_runtime, {**on, "ak": "A"}, {PresetMode.AUTO: {"ak": "A"}})
    assert auto.hvac_mode == HVACMode.AUTO

    vent, _ = _heater(hass, make_runtime, {**on, "vk": "V"}, {PresetMode.VENTILATION: {"vk": "V"}})
    assert vent.hvac_mode == HVACMode.FAN_ONLY

    heat, _ = _heater(hass, make_runtime, {**on, "lk": "L"}, {PresetMode.LOW: {"lk": "L"}})
    assert heat.hvac_mode == HVACMode.HEAT

    off, _ = _heater(hass, make_runtime, {PhilipsApi.NEW2_POWER: 0}, {})
    assert off.hvac_mode == HVACMode.OFF


async def test_climate_set_hvac_mode(hass: HomeAssistant, make_runtime) -> None:
    """Every supported hvac mode dispatches to the right command."""
    presets = {
        PresetMode.AUTO: {PhilipsApi.NEW2_POWER: 1, "m": "AG"},
        PresetMode.VENTILATION: {PhilipsApi.NEW2_POWER: 1, "m": "FF"},
        PresetMode.LOW: {PhilipsApi.NEW2_POWER: 1, "m": "L"},
    }
    heater, runtime = _heater(
        hass, make_runtime, {PhilipsApi.NEW2_POWER: 1}, presets, stub_write=True
    )

    await heater.async_set_hvac_mode(HVACMode.AUTO)
    await heater.async_set_hvac_mode(HVACMode.FAN_ONLY)
    await heater.async_set_hvac_mode(HVACMode.HEAT)
    await heater.async_set_hvac_mode(HVACMode.OFF)
    await heater.async_set_hvac_mode(HVACMode.DRY)  # unsupported -> no-op
    assert runtime.client.set_control_values.await_count >= 3


async def test_climate_preset_and_turn_on(hass: HomeAssistant, make_runtime) -> None:
    """Unknown presets are ignored; turn_on sends the on value."""
    heater, runtime = _heater(
        hass,
        make_runtime,
        {PhilipsApi.NEW2_POWER: 0},
        {PresetMode.AUTO: {"ak": "A"}},
        stub_write=True,
    )
    await heater.async_set_preset_mode("not-a-preset")  # status_pattern is None -> no-op
    runtime.client.set_control_values.assert_not_awaited()

    await heater.async_turn_on()
    runtime.client.set_control_value.assert_awaited_with(
        PhilipsApi.NEW2_POWER, heater.entity_description.on_value
    )


async def test_climate_swing_without_oscillation(hass: HomeAssistant, make_runtime) -> None:
    """A heater without oscillation has no swing mode and ignores swing calls."""
    heater, runtime = _heater(
        hass, make_runtime, {PhilipsApi.NEW2_POWER: 1}, {}, oscillation={}, stub_write=True
    )
    assert heater.swing_mode is None
    await heater.async_set_swing_mode(SWING_ON)  # no oscillation key -> no-op
    runtime.client.set_control_value.assert_not_awaited()


async def test_climate_swing_with_oscillation(hass: HomeAssistant, make_runtime) -> None:
    """A heater with oscillation reports and sets the swing mode."""
    oscillation = {"osc": {"on": 17920, "off": 0}}
    heater, runtime = _heater(
        hass,
        make_runtime,
        {PhilipsApi.NEW2_POWER: 1, "osc": 0},
        {},
        oscillation=oscillation,
        stub_write=True,
    )
    assert heater.swing_mode == SWING_OFF
    await heater.async_set_swing_mode(SWING_ON)
    runtime.client.set_control_value.assert_awaited_with("osc", 17920)
    # The optimistic update flipped the device on; the swing now reads on.
    assert heater.swing_mode == SWING_ON
    runtime.client.set_control_value.reset_mock()
    await heater.async_set_swing_mode("invalid")  # not a swing mode -> no-op
    runtime.client.set_control_value.assert_not_awaited()


# --------------------------------------------------------------------------- #
# humidifier.py
# --------------------------------------------------------------------------- #
def _humidifier(hass, make_runtime, desc, status, presets=None, stub_write=False):
    """Construct a PhilipsHumidifier with a given description and presets."""
    return _build(
        humidifier.PhilipsHumidifier,
        hass,
        make_runtime,
        status,
        desc,
        presets or {},
        model="AC2729",
        stub_write=stub_write,
    )


async def test_humidifier_unknown_model(hass: HomeAssistant, make_runtime) -> None:
    """An unknown model creates no humidifier."""
    entry, runtime = make_runtime(model="AC2729")
    runtime.device_information.model = "UNKNOWN9999"
    added: list = []
    await humidifier.async_setup_entry(hass, entry, lambda e, *_: added.extend(e))
    assert added == []


async def test_humidifier_switch_action_and_mode(hass: HomeAssistant, make_runtime) -> None:
    """The 2-in-1 humidifier reports action/mode and honours purification mode."""
    desc = _desc(humidifier.HUMIDIFIER_TYPES, PhilipsApi.HUMIDITY_TARGET)
    from homeassistant.components.humidifier import HumidifierAction

    # Humidifying state.
    on, _ = _humidifier(hass, make_runtime, desc, {PhilipsApi.FUNCTION: "PH"})
    assert on.action == HumidifierAction.HUMIDIFYING
    assert on.mode == FanFunction.PURIFICATION_HUMIDIFICATION

    # Idle / purification-only state.
    idle, runtime = _humidifier(
        hass, make_runtime, desc, {PhilipsApi.FUNCTION: "P"}, stub_write=True
    )
    assert idle.action == HumidifierAction.IDLE
    assert idle.mode == FanFunction.PURIFICATION

    await idle.async_set_mode(FanFunction.PURIFICATION)
    runtime.client.set_control_values.assert_awaited()
    await idle.async_set_mode("invalid-mode")  # ignored


async def test_humidifier_non_switch_modes(hass: HomeAssistant, make_runtime) -> None:
    """A non-switch humidifier whose function differs from power has no mode."""
    desc = _desc(humidifier.HUMIDIFIER_TYPES, PhilipsApi.NEW2_HUMIDITY_TARGET)
    ent, _ = _humidifier(hass, make_runtime, desc, {PhilipsApi.NEW2_POWER: 1})
    assert ent._attr_available_modes is None
    assert ent.mode is None


async def test_humidifier_pure_mode_loop(hass: HomeAssistant, make_runtime) -> None:
    """A pure humidifier resolves its mode by scanning the preset patterns."""
    desc = _desc(humidifier.HUMIDIFIER_TYPES, PhilipsApi.NEW2_HUMIDITY_TARGET2)
    presets = {
        "auto": {PhilipsApi.NEW2_POWER: 1, "x": 5},
        "low": {PhilipsApi.NEW2_POWER: 1, "x": 9},
    }
    ent, _ = _humidifier(hass, make_runtime, desc, {PhilipsApi.NEW2_POWER: 1, "x": 9}, presets)
    assert ent.mode == "low"


async def test_humidifier_set_humidity_nudges(hass: HomeAssistant, make_runtime) -> None:
    """A +/-1 nudge snaps to a full step; a missing target is handled."""
    desc = _desc(humidifier.HUMIDIFIER_TYPES, PhilipsApi.HUMIDITY_TARGET)  # step 10

    # No current target stored -> no nudge, value rounded to the step.
    ent_none, runtime_none = _humidifier(hass, make_runtime, desc, {}, stub_write=True)
    await ent_none.async_set_humidity(52)
    runtime_none.client.set_control_value.assert_awaited_with(PhilipsApi.HUMIDITY_TARGET, 50)

    # +1 from the current target snaps up a full step.
    ent_up, runtime_up = _humidifier(
        hass, make_runtime, desc, {PhilipsApi.HUMIDITY_TARGET: 50}, stub_write=True
    )
    await ent_up.async_set_humidity(51)
    runtime_up.client.set_control_value.assert_awaited_with(PhilipsApi.HUMIDITY_TARGET, 60)

    # -1 from the current target snaps down a full step.
    ent_down, runtime_down = _humidifier(
        hass, make_runtime, desc, {PhilipsApi.HUMIDITY_TARGET: 50}, stub_write=True
    )
    await ent_down.async_set_humidity(49)
    runtime_down.client.set_control_value.assert_awaited_with(PhilipsApi.HUMIDITY_TARGET, 40)


# --------------------------------------------------------------------------- #
# config_flow.py
# --------------------------------------------------------------------------- #
_CF_STATUS = {
    **_BASE,
    PhilipsApi.MODEL_ID: "AC3033/10",
    PhilipsApi.NAME: "Living Room",
}


def test_host_valid_variants() -> None:
    """host_valid accepts IPs and hostnames, rejects malformed strings."""
    from custom_components.philips_airpurifier_coap.config_flow import host_valid

    assert host_valid("192.168.1.5")
    assert host_valid("fe80::1")
    assert host_valid("my-purifier")  # hostname path (ip_address raises ValueError)
    assert not host_valid("bad host!")
    assert not host_valid("")


def _cf_client(status=_CF_STATUS):
    """Patch the config-flow CoAP client to return a given status."""
    client = AsyncMock()
    client.get_status = AsyncMock(return_value=(dict(status), 60))
    client.shutdown = AsyncMock()
    return patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(return_value=client),
    )


async def _menu_to(hass: HomeAssistant, step: str):
    """Open the user menu and pick a branch."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": step})


async def test_manual_flow_connection_error(hass: HomeAssistant, bypass_integration_deps) -> None:
    """A connection failure during manual entry keeps the form open with an error."""
    result = await _menu_to(hass, "manual")
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(side_effect=OSError("boom")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_HOST] == "connect"


async def test_manual_flow_unsupported_model(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An unsupported model aborts the manual flow."""
    result = await _menu_to(hass, "manual")
    status = {**_CF_STATUS, PhilipsApi.MODEL_ID: "ZZ9999/10"}
    with _cf_client(status):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "model_unsupported"


async def test_ssdp_flow_host_from_location(hass: HomeAssistant, bypass_integration_deps) -> None:
    """SSDP falls back to the location URL for the host, then aborts on error."""
    info = SsdpServiceInfo(
        ssdp_usn="usn",
        ssdp_st="st",
        ssdp_location="http://1.2.3.4:80/desc.xml",
        upnp={},
        ssdp_headers={},  # no _host -> must be parsed from the location
    )
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(side_effect=OSError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=info
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "timeout"


async def test_ssdp_flow_unsupported_model(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An unsupported model aborts the SSDP flow."""
    info = SsdpServiceInfo(
        ssdp_usn="usn",
        ssdp_st="st",
        ssdp_location="http://1.2.3.4/",
        upnp={},
        ssdp_headers={"_host": "1.2.3.4"},
    )
    with _cf_client({**_CF_STATUS, PhilipsApi.MODEL_ID: "ZZ9999/10"}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=info
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "model_unsupported"


async def test_pick_second_device(hass: HomeAssistant, bypass_integration_deps) -> None:
    """Picking a non-first discovered device skips past the others in the loop."""
    devices = [
        {"ip": "1.2.3.4", "model": "AC3033/10", "name": "A", "status": _CF_STATUS},
        {
            "ip": "1.2.3.5",
            "model": "AC3033/10",
            "name": "B",
            "status": {**_CF_STATUS, PhilipsApi.DEVICE_ID: "SECONDDEVICE01"},
        },
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

    assert result["step_id"] == "pick_device"
    # Selecting the second device makes the lookup loop skip the first one.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "1.2.3.5"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "SECONDDEVICE01"


async def test_reconfigure_connection_error(hass: HomeAssistant, bypass_integration_deps) -> None:
    """An unexpected error while reconfiguring keeps the form open with an error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ABCD1234567890",
        title="AC3033 Living Room",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_MODEL: "AC3033",
            CONF_NAME: "Living Room",
            CONF_DEVICE_ID: "ABCD1234567890",
            CONF_STATUS: _CF_STATUS,
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch(
        "custom_components.philips_airpurifier_coap.config_flow.CoAPClient.create",
        AsyncMock(side_effect=OSError("boom")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.8"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_HOST] == "connect"
