"""Collection of classes to manage Philips AirPurifier devices."""
from __future__ import annotations

import asyncio
from asyncio.tasks import Task
from collections.abc import Callable
import contextlib
from datetime import timedelta
import logging
from typing import Any, Optional, Union

from aioairctrl import CoAPClient

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import (
    DOMAIN,
    ICON,
    SWITCH_OFF,
    SWITCH_ON,
    FanAttributes,
    FanModel,
    PhilipsApi,
    PresetMode,
)
from .model import DeviceStatus
from .timer import Timer

_LOGGER = logging.getLogger(__name__)

MISSED_PACKAGE_COUNT = 3


class Coordinator:
    """Class to coordinate the data requests from the Philips API."""

    def __init__(self, client: CoAPClient, host: str, mac: str) -> None:  # noqa: D107
        self.client = client
        self._host = host
        self._mac = mac

        # It's None before the first successful update.
        # Components should call async_first_refresh to make sure the first
        # update was successful. Set type to just DeviceStatus to remove
        # annoying checks that status is not None when it was already checked
        # during setup.
        self.status: DeviceStatus = None  # type: ignore[assignment]

        self._listeners: list[CALLBACK_TYPE] = []
        self._task: Task | None = None

        self._reconnect_task: Task | None = None
        self._timeout: int = 60

        # Timeout = MAX_AGE * 3 Packet losses
        _LOGGER.debug("init: Creating and autostarting timer for host %s", self._host)
        self._timer_disconnected = Timer(
            timeout=self._timeout * MISSED_PACKAGE_COUNT,
            callback=self.reconnect,
            autostart=True,
        )
        self._timer_disconnected._auto_restart = True
        _LOGGER.debug("init: finished for host %s", self._host)

    async def shutdown(self):
        """Shutdown the API connection."""
        _LOGGER.debug("shutdown: called for host %s", self._host)
        if self._reconnect_task is not None:
            _LOGGER.debug("shutdown: cancelling reconnect task for host %s", self._host)
            self._reconnect_task.cancel()
        if self._timer_disconnected is not None:
            _LOGGER.debug("shutdown: cancelling timeout task for host %s", self._host)
            self._timer_disconnected.cancel()
        if self.client is not None:
            await self.client.shutdown()

    async def reconnect(self):
        """Reconnect to the API connection."""
        _LOGGER.debug("reconnect: called for host %s", self._host)
        try:
            if self._reconnect_task is not None:
                # Reconnect stuck
                _LOGGER.debug(
                    "reconnect: cancelling reconnect task for host %s", self._host
                )
                self._reconnect_task.cancel()
                self._reconnect_task = None
            # Reconnect in new Task, keep timer watching
            _LOGGER.debug(
                "reconnect: creating new reconnect task for host %s", self._host
            )
            self._reconnect_task = asyncio.create_task(self._reconnect())
        except:  # noqa: E722
            _LOGGER.exception("Exception on starting reconnect!")

    async def _reconnect(self):
        try:
            _LOGGER.debug("Reconnecting")
            with contextlib.suppress(Exception):
                await self.client.shutdown()
            self.client = await CoAPClient.create(self._host)
            self._start_observing()
        except asyncio.CancelledError:
            # Silently drop this exception, because we are responsible for it.
            # Reconnect took to long
            pass
        except:  # noqa: E722
            _LOGGER.exception("_reconnect error")

    async def async_first_refresh(self) -> None:
        """Refresh the data for the first time."""
        _LOGGER.debug("async_first_refresh for host %s", self._host)
        try:
            self.status, timeout = await self.client.get_status()
            self._timeout = timeout
            if self._timer_disconnected is not None:
                self._timer_disconnected.setTimeout(timeout * MISSED_PACKAGE_COUNT)
            _LOGGER.debug("finished first refresh for host %s", self._host)
        except Exception as ex:
            _LOGGER.error(
                "Config not ready, first refresh failed for host %s", self._host
            )
            raise ConfigEntryNotReady from ex

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        """Listen for data updates."""
        start_observing = not self._listeners

        self._listeners.append(update_callback)

        if start_observing:
            self._start_observing()

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self.async_remove_listener(update_callback)

        return remove_listener

    @callback
    def async_remove_listener(self, update_callback) -> None:
        """Remove data update."""
        self._listeners.remove(update_callback)

        if not self._listeners and self._task:
            self._task.cancel()
            self._task = None

    async def _async_observe_status(self) -> None:
        async for status in self.client.observe_status():
            _LOGGER.debug("Status update: %s", status)
            self.status = status
            self._timer_disconnected.reset()
            for update_callback in self._listeners:
                update_callback()

    def _start_observing(self) -> None:
        """Schedule state observation."""
        if self._task:
            self._task.cancel()
            self._task = None
        self._task = asyncio.create_task(self._async_observe_status())
        self._timer_disconnected.reset()


class PhilipsEntity(Entity):
    """Class to represent a generic Philips entity."""

    def __init__(self, coordinator: Coordinator) -> None:  # noqa: D107
        super().__init__()
        _LOGGER.debug("PhilipsEntity __init__ called")
        _LOGGER.debug("coordinator.status is: %s", coordinator.status)
        self.coordinator = coordinator
        self._serialNumber = coordinator.status[PhilipsApi.DEVICE_ID]
        # self._name = coordinator.status["name"]
        self._name = list(
            filter(
                None,
                map(
                    coordinator.status.get,
                    [PhilipsApi.NAME, PhilipsApi.NEW_NAME, PhilipsApi.NEW2_NAME],
                ),
            )
        )[0]
        # self._modelName = coordinator.status["modelid"]
        self._modelName = list(
            filter(
                None,
                map(
                    coordinator.status.get,
                    [
                        PhilipsApi.MODEL_ID,
                        PhilipsApi.NEW_MODEL_ID,
                        PhilipsApi.NEW2_MODEL_ID,
                    ],
                ),
            )
        )[0]
        self._firmware = coordinator.status["WifiVersion"]
        self._manufacturer = "Philips"
        self._mac = coordinator._mac

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return info about the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serialNumber)},
            connections={(CONNECTION_NETWORK_MAC, self._mac)}
            if self._mac is not None
            else None,
            name=self._name,
            model=self._modelName,
            manufacturer=self._manufacturer,
            sw_version=self._firmware,
        )

    @property
    def available(self):
        """Return if the device is available."""
        return self.coordinator.status is not None

    @property
    def _device_status(self) -> dict[str, Any]:
        """Return the status of the device."""
        return self.coordinator.status

    async def async_added_to_hass(self) -> None:
        """Register with hass that routine got added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class PhilipsGenericFan(PhilipsEntity, FanEntity):
    """Class to manage a generic Philips fan."""

    def __init__(  # noqa: D107
        self,
        coordinator: Coordinator,
        model: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._model = model
        self._name = name
        self._unique_id = None

    @property
    def unique_id(self) -> Optional[str]:
        """Return the unique ID of the fan."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the fan."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon of the fan."""
        return self._icon


class PhilipsGenericCoAPFanBase(PhilipsGenericFan):
    """Class as basis to manage a generic Philips CoAP fan."""

    AVAILABLE_PRESET_MODES = {}
    REPLACE_PRESET = None
    AVAILABLE_SPEEDS = {}
    REPLACE_SPEED = None
    AVAILABLE_ATTRIBUTES = []
    AVAILABLE_SWITCHES = []
    AVAILABLE_LIGHTS = []
    AVAILABLE_NUMBERS = []
    AVAILABLE_BINARY_SENSORS = []

    KEY_PHILIPS_POWER = PhilipsApi.POWER
    STATE_POWER_ON = "1"
    STATE_POWER_OFF = "0"

    KEY_OSCILLATION = None

    def __init__(  # noqa: D107
        self,
        coordinator: Coordinator,
        model: str,
        name: str,
    ) -> None:
        super().__init__(coordinator, model, name)

        self._preset_modes = []
        self._available_preset_modes = {}
        self._collect_available_preset_modes()

        self._speeds = []
        self._available_speeds = {}
        self._collect_available_speeds()

        self._available_attributes = []
        self._collect_available_attributes()

        try:
            device_id = self._device_status[PhilipsApi.DEVICE_ID]
            self._unique_id = f"{self._model}-{device_id}"
        except Exception as e:
            _LOGGER.error("Failed retrieving unique_id: %s", e)
            raise PlatformNotReady

    def _collect_available_preset_modes(self):
        preset_modes = {}
        for cls in reversed(self.__class__.__mro__):
            cls_preset_modes = getattr(cls, "AVAILABLE_PRESET_MODES", {})
            preset_modes.update(cls_preset_modes)
        self._available_preset_modes = preset_modes
        self._preset_modes = list(self._available_preset_modes.keys())

    def _collect_available_speeds(self):
        speeds = {}
        for cls in reversed(self.__class__.__mro__):
            cls_speeds = getattr(cls, "AVAILABLE_SPEEDS", {})
            speeds.update(cls_speeds)
        self._available_speeds = speeds
        self._speeds = list(self._available_speeds.keys())

    def _collect_available_attributes(self):
        attributes = []
        for cls in reversed(self.__class__.__mro__):
            cls_attributes = getattr(cls, "AVAILABLE_ATTRIBUTES", [])
            attributes.extend(cls_attributes)
        self._available_attributes = attributes

    @property
    def is_on(self) -> bool:
        """Return if the fan is on."""
        status = self._device_status.get(self.KEY_PHILIPS_POWER)
        # _LOGGER.debug("is_on: status=%s - test=%s", status, self.STATE_POWER_ON)
        return status == self.STATE_POWER_ON

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ):
        """Turn the fan on."""
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
            return
        if percentage:
            await self.async_set_percentage(percentage)
            return
        await self.coordinator.client.set_control_value(
            self.KEY_PHILIPS_POWER, self.STATE_POWER_ON
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        await self.coordinator.client.set_control_value(
            self.KEY_PHILIPS_POWER, self.STATE_POWER_OFF
        )

    @property
    def supported_features(self) -> int:
        """Return the supported features."""
        features = FanEntityFeature.PRESET_MODE
        if self._speeds:
            features |= FanEntityFeature.SET_SPEED
        if self.KEY_OSCILLATION is not None:
            features |= FanEntityFeature.OSCILLATE
        return features

    @property
    def preset_modes(self) -> Optional[list[str]]:
        """Return the supported preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the selected preset mode."""
        for preset_mode, status_pattern in self._available_preset_modes.items():
            for k, v in status_pattern.items():
                # check if the speed sensor also used for presets is different from the setting field
                if self.REPLACE_PRESET is not None and k == self.REPLACE_PRESET[0]:
                    k = self.REPLACE_PRESET[1]
                status = self._device_status.get(k)
                if status != v:
                    break
            else:
                return preset_mode

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        status_pattern = self._available_preset_modes.get(preset_mode)
        if status_pattern:
            await self.coordinator.client.set_control_values(data=status_pattern)

    @property
    def speed_count(self) -> int:
        """Return the number of speed options."""
        return len(self._speeds)

    @property
    def oscillating(self) -> bool | None:
        """Return if the fan is oscillating."""
        if self.KEY_OSCILLATION is None:
            return None

        key = next(iter(self.KEY_OSCILLATION))
        status = self._device_status.get(key)
        on = self.KEY_OSCILLATION.get(key).get(SWITCH_ON)
        return status is not None and status == on

    async def async_oscillate(self, oscillating: bool) -> None:
        """Osciallate the fan."""
        if self.KEY_OSCILLATION is None:
            return None

        key = next(iter(self.KEY_OSCILLATION))
        values = self.KEY_OSCILLATION.get(key)
        on = values.get(SWITCH_ON)
        off = values.get(SWITCH_OFF)
        if oscillating:
            await self.coordinator.client.set_control_value(key, on)
        else:
            await self.coordinator.client.set_control_value(key, off)

    @property
    def percentage(self) -> Optional[int]:
        """Return the speed percentages."""
        for speed, status_pattern in self._available_speeds.items():
            for k, v in status_pattern.items():
                # check if the speed sensor is different from the speed setting field
                if self.REPLACE_SPEED is not None and k == self.REPLACE_SPEED[0]:
                    k = self.REPLACE_SPEED[1]
                if self._device_status.get(k) != v:
                    break
            else:
                return ordered_list_item_to_percentage(self._speeds, speed)

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Return the selected speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
        else:
            speed = percentage_to_ordered_list_item(self._speeds, percentage)
            status_pattern = self._available_speeds.get(speed)
            if status_pattern:
                await self.coordinator.client.set_control_values(data=status_pattern)

    @property
    def extra_state_attributes(self) -> Optional[dict[str, Any]]:
        """Return the extra state attributes."""

        def append(
            attributes: dict,
            key: str,
            philips_key: str,
            value_map: Union[dict, Callable[[Any, Any], Any]] = None,
        ):
            # some philips keys are not unique, so # serves as a marker and needs to be filtered out
            philips_clean_key = philips_key.partition("#")[0]

            if philips_clean_key in self._device_status:
                value = self._device_status[philips_clean_key]
                if isinstance(value_map, dict) and value in value_map:
                    value = value_map.get(value, "unknown")
                    if isinstance(value, tuple):
                        value = value[0]
                elif callable(value_map):
                    value = value_map(value, self._device_status)
                attributes.update({key: value})

        device_attributes = {}
        for key, philips_key, *rest in self._available_attributes:
            value_map = rest[0] if len(rest) else None
            append(device_attributes, key, philips_key, value_map)
        return device_attributes

    @property
    def icon(self) -> str:
        """Return the icon of the fan."""
        if not self.is_on:
            return ICON.POWER_BUTTON

        preset_mode = self.preset_mode
        if preset_mode is None:
            return ICON.FAN_SPEED_BUTTON
        if preset_mode in PresetMode.ICON_MAP:
            return PresetMode.ICON_MAP[preset_mode]

        return ICON.FAN_SPEED_BUTTON


class PhilipsGenericCoAPFan(PhilipsGenericCoAPFanBase):
    """Class to manage a generic Philips CoAP fan."""

    AVAILABLE_PRESET_MODES = {}
    AVAILABLE_SPEEDS = {}

    AVAILABLE_ATTRIBUTES = [
        # device information
        (FanAttributes.NAME, PhilipsApi.NAME),
        (FanAttributes.TYPE, PhilipsApi.TYPE),
        (FanAttributes.MODEL_ID, PhilipsApi.MODEL_ID),
        (FanAttributes.PRODUCT_ID, PhilipsApi.PRODUCT_ID),
        (FanAttributes.DEVICE_ID, PhilipsApi.DEVICE_ID),
        (FanAttributes.DEVICE_VERSION, PhilipsApi.DEVICE_VERSION),
        (FanAttributes.SOFTWARE_VERSION, PhilipsApi.SOFTWARE_VERSION),
        (FanAttributes.WIFI_VERSION, PhilipsApi.WIFI_VERSION),
        (FanAttributes.ERROR_CODE, PhilipsApi.ERROR_CODE),
        # (FanAttributes.ERROR, PhilipsApi.ERROR_CODE, PhilipsApi.ERROR_CODE_MAP),
        # device configuration
        (FanAttributes.LANGUAGE, PhilipsApi.LANGUAGE),
        (
            FanAttributes.PREFERRED_INDEX,
            PhilipsApi.PREFERRED_INDEX,
            PhilipsApi.PREFERRED_INDEX_MAP,
        ),
        # device sensors
        (
            FanAttributes.RUNTIME,
            PhilipsApi.RUNTIME,
            lambda x, _: str(timedelta(seconds=round(x / 1000))),
        ),
    ]

    AVAILABLE_LIGHTS = [PhilipsApi.DISPLAY_BACKLIGHT, PhilipsApi.LIGHT_BRIGHTNESS]

    AVAILABLE_SWITCHES = []
    AVAILABLE_SELECTS = []


class PhilipsNewGenericCoAPFan(PhilipsGenericCoAPFanBase):
    """Class to manage a new generic CoAP fan."""

    AVAILABLE_PRESET_MODES = {}
    AVAILABLE_SPEEDS = {}

    AVAILABLE_ATTRIBUTES = [
        # device information
        (FanAttributes.NAME, PhilipsApi.NEW_NAME),
        (FanAttributes.MODEL_ID, PhilipsApi.NEW_MODEL_ID),
        (FanAttributes.PRODUCT_ID, PhilipsApi.PRODUCT_ID),
        (FanAttributes.DEVICE_ID, PhilipsApi.DEVICE_ID),
        (FanAttributes.SOFTWARE_VERSION, PhilipsApi.NEW_SOFTWARE_VERSION),
        (FanAttributes.WIFI_VERSION, PhilipsApi.WIFI_VERSION),
        # (FanAttributes.ERROR_CODE, PhilipsApi.ERROR_CODE),
        # (FanAttributes.ERROR, PhilipsApi.ERROR_CODE, PhilipsApi.ERROR_CODE_MAP),
        # device configuration
        (FanAttributes.LANGUAGE, PhilipsApi.NEW_LANGUAGE),
        (
            FanAttributes.PREFERRED_INDEX,
            PhilipsApi.NEW_PREFERRED_INDEX,
            PhilipsApi.NEW_PREFERRED_INDEX_MAP,
        ),
        # device sensors
        (
            FanAttributes.RUNTIME,
            PhilipsApi.RUNTIME,
            lambda x, _: str(timedelta(seconds=round(x / 1000))),
        ),
    ]

    AVAILABLE_LIGHTS = []
    AVAILABLE_SWITCHES = []
    AVAILABLE_SELECTS = [PhilipsApi.NEW_PREFERRED_INDEX]

    KEY_PHILIPS_POWER = PhilipsApi.NEW_POWER
    STATE_POWER_ON = "ON"
    STATE_POWER_OFF = "OFF"


class PhilipsNew2GenericCoAPFan(PhilipsGenericCoAPFanBase):
    """Class to manage another new generic CoAP fan."""

    AVAILABLE_PRESET_MODES = {}
    AVAILABLE_SPEEDS = {}

    AVAILABLE_ATTRIBUTES = [
        # device information
        (FanAttributes.NAME, PhilipsApi.NEW2_NAME),
        (FanAttributes.MODEL_ID, PhilipsApi.NEW2_MODEL_ID),
        (FanAttributes.PRODUCT_ID, PhilipsApi.PRODUCT_ID),
        (FanAttributes.DEVICE_ID, PhilipsApi.DEVICE_ID),
        (FanAttributes.SOFTWARE_VERSION, PhilipsApi.NEW2_SOFTWARE_VERSION),
        (FanAttributes.WIFI_VERSION, PhilipsApi.WIFI_VERSION),
        (FanAttributes.ERROR_CODE, PhilipsApi.NEW2_ERROR_CODE),
        # (FanAttributes.ERROR, PhilipsApi.ERROR_CODE, PhilipsApi.ERROR_CODE_MAP),
        # device configuration
        (
            FanAttributes.PREFERRED_INDEX,
            PhilipsApi.NEW2_GAS_PREFERRED_INDEX,
            PhilipsApi.GAS_PREFERRED_INDEX_MAP,
        ),
        # device sensors
        (
            FanAttributes.RUNTIME,
            PhilipsApi.RUNTIME,
            lambda x, _: str(timedelta(seconds=round(x / 1000))),
        ),
    ]

    AVAILABLE_LIGHTS = []
    AVAILABLE_SWITCHES = []
    AVAILABLE_SELECTS = []

    KEY_PHILIPS_POWER = PhilipsApi.NEW2_POWER
    STATE_POWER_ON = 1
    STATE_POWER_OFF = 0


class PhilipsHumidifierMixin(PhilipsGenericCoAPFanBase):
    """Mixin for humidifiers."""

    AVAILABLE_SELECTS = [PhilipsApi.FUNCTION, PhilipsApi.HUMIDITY_TARGET]
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.ERROR_CODE]


# similar to the AC1715, the AC0850 seems to be a new class of devices that
# follows some patterns of its own
class PhilipsAC0850(PhilipsNewGenericCoAPFan):
    """AC0850."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW_POWER: "ON",
            PhilipsApi.NEW_MODE: "Auto General",
        },
        PresetMode.TURBO: {PhilipsApi.NEW_POWER: "ON", PhilipsApi.NEW_MODE: "Turbo"},
        PresetMode.SLEEP: {PhilipsApi.NEW_POWER: "ON", PhilipsApi.NEW_MODE: "Sleep"},
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {PhilipsApi.NEW_POWER: "ON", PhilipsApi.NEW_MODE: "Sleep"},
        PresetMode.TURBO: {PhilipsApi.NEW_POWER: "ON", PhilipsApi.NEW_MODE: "Turbo"},
    }
    # the prefilter data is present but doesn't change for this device, so let's take it out
    UNAVAILABLE_FILTERS = [PhilipsApi.FILTER_NANOPROTECT_PREFILTER]


# the AC1715 seems to be a new class of devices that follows some patterns of its own
class PhilipsAC1715(PhilipsNewGenericCoAPFan):
    """AC1715."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW_POWER: "ON",
            PhilipsApi.NEW_MODE: "Auto General",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.NEW_POWER: "ON",
            PhilipsApi.NEW_MODE: "Gentle/Speed 1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.NEW_POWER: "ON",
            PhilipsApi.NEW_MODE: "Speed 2",
        },
        PresetMode.TURBO: {PhilipsApi.NEW_POWER: "ON", PhilipsApi.NEW_MODE: "Turbo"},
        PresetMode.SLEEP: {PhilipsApi.NEW_POWER: "ON", PhilipsApi.NEW_MODE: "Sleep"},
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {PhilipsApi.NEW_POWER: "ON", PhilipsApi.NEW_MODE: "Sleep"},
        PresetMode.SPEED_1: {
            PhilipsApi.NEW_POWER: "ON",
            PhilipsApi.NEW_MODE: "Gentle/Speed 1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.NEW_POWER: "ON",
            PhilipsApi.NEW_MODE: "Speed 2",
        },
        PresetMode.TURBO: {PhilipsApi.NEW_POWER: "ON", PhilipsApi.NEW_MODE: "Turbo"},
    }
    AVAILABLE_LIGHTS = [PhilipsApi.NEW_DISPLAY_BACKLIGHT]


class PhilipsAC1214(PhilipsGenericCoAPFan):
    """AC1214."""

    # the AC1214 doesn't seem to like a power on call when the mode or speed is set,
    # so this needs to be handled separately
    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.MODE: "P"},
        PresetMode.ALLERGEN: {PhilipsApi.MODE: "A"},
        # make speeds available as preset
        PresetMode.NIGHT: {PhilipsApi.MODE: "N"},
        PresetMode.SPEED_1: {PhilipsApi.MODE: "M", PhilipsApi.SPEED: "1"},
        PresetMode.SPEED_2: {PhilipsApi.MODE: "M", PhilipsApi.SPEED: "2"},
        PresetMode.SPEED_3: {PhilipsApi.MODE: "M", PhilipsApi.SPEED: "3"},
        PresetMode.TURBO: {PhilipsApi.MODE: "M", PhilipsApi.SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PresetMode.NIGHT: {PhilipsApi.MODE: "N"},
        PresetMode.SPEED_1: {PhilipsApi.MODE: "M", PhilipsApi.SPEED: "1"},
        PresetMode.SPEED_2: {PhilipsApi.MODE: "M", PhilipsApi.SPEED: "2"},
        PresetMode.SPEED_3: {PhilipsApi.MODE: "M", PhilipsApi.SPEED: "3"},
        PresetMode.TURBO: {PhilipsApi.MODE: "M", PhilipsApi.SPEED: "t"},
    }
    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]
    AVAILABLE_SELECTS = [PhilipsApi.PREFERRED_INDEX]

    async def async_set_a(self) -> None:
        """Set the preset mode to Allergen."""
        _LOGGER.debug("AC1214 switches to mode 'A' first")
        a_status_pattern = self._available_preset_modes.get(PresetMode.ALLERGEN)
        await self.coordinator.client.set_control_values(data=a_status_pattern)
        await asyncio.sleep(1)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("AC1214 async_set_preset_mode is called with: %s", preset_mode)

        # the AC1214 doesn't like it if we set a preset mode to switch on the device,
        # so it needs to be done in sequence
        if not self.is_on:
            _LOGGER.debug("AC1214 is switched on without setting a mode")
            await self.coordinator.client.set_control_value(
                PhilipsApi.POWER, PhilipsApi.POWER_MAP[SWITCH_ON]
            )
            await asyncio.sleep(1)

        # the AC1214 also doesn't seem to like switching to mode 'M' without cycling through mode 'A'
        current_pattern = self._available_preset_modes.get(self.preset_mode)
        _LOGGER.debug("AC1214 is currently on mode: %s", current_pattern)
        if preset_mode:
            _LOGGER.debug("AC1214 preset mode requested: %s", preset_mode)
            status_pattern = self._available_preset_modes.get(preset_mode)
            _LOGGER.debug("this corresponds to status pattern: %s", status_pattern)
            if (
                status_pattern
                and status_pattern.get(PhilipsApi.MODE) != "A"
                and current_pattern.get(PhilipsApi.MODE) != "M"
            ):
                await self.async_set_a()
            _LOGGER.debug("AC1214 sets preset mode to: %s", preset_mode)
            if status_pattern:
                await self.coordinator.client.set_control_values(data=status_pattern)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("AC1214 async_set_percentage is called with: %s", percentage)

        # the AC1214 doesn't like it if we set a preset mode to switch on the device,
        # so it needs to be done in sequence
        if not self.is_on:
            _LOGGER.debug("AC1214 is switched on without setting a mode")
            await self.coordinator.client.set_control_value(
                PhilipsApi.POWER, PhilipsApi.POWER_MAP[SWITCH_ON]
            )
            await asyncio.sleep(1)

        current_pattern = self._available_preset_modes.get(self.preset_mode)
        _LOGGER.debug("AC1214 is currently on mode: %s", current_pattern)
        if percentage == 0:
            _LOGGER.debug("AC1214 uses 0% to switch off")
            await self.async_turn_off()
        else:
            # the AC1214 also doesn't seem to like switching to mode 'M' without cycling through mode 'A'
            _LOGGER.debug("AC1214 speed change requested: %s", percentage)
            speed = percentage_to_ordered_list_item(self._speeds, percentage)
            status_pattern = self._available_speeds.get(speed)
            _LOGGER.debug("this corresponds to status pattern: %s", status_pattern)
            if (
                status_pattern
                and status_pattern.get(PhilipsApi.MODE) != "A"
                and current_pattern.get(PhilipsApi.MODE) != "M"
            ):
                await self.async_set_a()
            _LOGGER.debug("AC1214 sets speed percentage to: %s", percentage)
            if status_pattern:
                await self.coordinator.client.set_control_values(data=status_pattern)

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ):
        """Turn on the device."""
        _LOGGER.debug(
            "AC1214 async_turn_on called with percentage=%s and preset_mode=%s",
            percentage,
            preset_mode,
        )
        # the AC1214 doesn't like it if we set a preset mode to switch on the device,
        # so it needs to be done in sequence
        if not self.is_on:
            _LOGGER.debug("AC1214 is switched on without setting a mode")
            await self.coordinator.client.set_control_value(
                PhilipsApi.POWER, PhilipsApi.POWER_MAP[SWITCH_ON]
            )
            await asyncio.sleep(1)

        if preset_mode:
            _LOGGER.debug("AC1214 preset mode requested: %s", preset_mode)
            await self.async_set_preset_mode(preset_mode)
            return
        if percentage:
            _LOGGER.debug("AC1214 speed change requested: %s", percentage)
            await self.async_set_percentage(percentage)
            return


class PhilipsAC2729(
    PhilipsHumidifierMixin,
    PhilipsGenericCoAPFan,
):
    """AC2729."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "P"},
        PresetMode.ALLERGEN: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "A"},
        # make speeds available as preset
        PresetMode.NIGHT: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.NIGHT: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]
    AVAILABLE_SELECTS = [PhilipsApi.PREFERRED_INDEX]


class PhilipsAC2889(PhilipsGenericCoAPFan):
    """AC2889."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "P"},
        PresetMode.ALLERGEN: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "A"},
        PresetMode.BACTERIA: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "B"},
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SELECTS = [PhilipsApi.PREFERRED_INDEX]


class PhilipsAC29xx(PhilipsGenericCoAPFan):
    """AC29xx family."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "AG"},
        PresetMode.SLEEP: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "S"},
        PresetMode.GENTLE: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "GT"},
        PresetMode.TURBO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "T"},
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "S"},
        PresetMode.GENTLE: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "GT"},
        PresetMode.TURBO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "T"},
    }
    AVAILABLE_SELECTS = [PhilipsApi.PREFERRED_INDEX]
    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]


class PhilipsAC2936(PhilipsAC29xx):
    """AC2936."""


class PhilipsAC2939(PhilipsAC29xx):
    """AC2939."""


class PhilipsAC2958(PhilipsAC29xx):
    """AC2958."""


class PhilipsAC2959(PhilipsAC29xx):
    """AC2959."""


class PhilipsAC303x(PhilipsGenericCoAPFan):
    """AC30xx family."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "AG"},
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SLEEP_ALLERGY: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "AS",
            PhilipsApi.SPEED: "as",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SELECTS = [PhilipsApi.GAS_PREFERRED_INDEX]


class PhilipsAC3033(PhilipsAC303x):
    """AC3033."""


class PhilipsAC3036(PhilipsAC303x):
    """AC3036."""


class PhilipsAC3039(PhilipsAC303x):
    """AC3039."""


class PhilipsAC305x(PhilipsGenericCoAPFan):
    """AC305x family."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "AG"},
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SELECTS = [PhilipsApi.GAS_PREFERRED_INDEX]


class PhilipsAC3055(PhilipsAC305x):
    """AC3055."""


class PhilipsAC3059(PhilipsAC305x):
    """AC3059."""


class PhilipsAC3259(PhilipsGenericCoAPFan):
    """AC3259."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "P"},
        PresetMode.ALLERGEN: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "A"},
        PresetMode.BACTERIA: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "B"},
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SELECTS = [PhilipsApi.GAS_PREFERRED_INDEX]


class PhilipsAC3737(PhilipsNew2GenericCoAPFan):
    """AC3737."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 2,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.SLEEP: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 2,
            PhilipsApi.NEW2_MODE_B: 17,
        },
        PresetMode.TURBO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 18,
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 2,
            PhilipsApi.NEW2_MODE_B: 17,
        },
        PresetMode.SPEED_1: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 2,
            PhilipsApi.NEW2_MODE_B: 1,
        },
        PresetMode.SPEED_2: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 2,
            PhilipsApi.NEW2_MODE_B: 2,
        },
        PresetMode.TURBO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 18,
        },
    }

    AVAILABLE_SELECTS = [PhilipsApi.NEW2_HUMIDITY_TARGET]
    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT2]
    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_CHILD_LOCK]
    UNAVAILABLE_SENSORS = [PhilipsApi.NEW2_FAN_SPEED]
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.NEW2_ERROR_CODE, PhilipsApi.NEW2_MODE_A]


class PhilipsAC3829(PhilipsHumidifierMixin, PhilipsGenericCoAPFan):
    """AC3829."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "P"},
        PresetMode.ALLERGEN: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "A"},
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]
    AVAILABLE_SELECTS = [PhilipsApi.GAS_PREFERRED_INDEX]


class PhilipsAC3836(PhilipsGenericCoAPFan):
    """AC3836."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "AG",
            PhilipsApi.SPEED: "1",
        },
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SELECTS = [PhilipsApi.GAS_PREFERRED_INDEX]


class PhilipsAC385x50(PhilipsGenericCoAPFan):
    """AC385x/50 family."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "AG"},
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SELECTS = [PhilipsApi.GAS_PREFERRED_INDEX]


class PhilipsAC385450(PhilipsAC385x50):
    """AC3854/50."""


class PhilipsAC385850(PhilipsAC385x50):
    """AC3858/50."""


class PhilipsAC385x51(PhilipsGenericCoAPFan):
    """AC385x/51 family."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "AG"},
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SLEEP_ALLERGY: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "AS",
            PhilipsApi.SPEED: "as",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]
    AVAILABLE_SELECTS = [PhilipsApi.GAS_PREFERRED_INDEX]


class PhilipsAC385451(PhilipsAC385x51):
    """AC3854/51."""


class PhilipsAC385851(PhilipsAC385x51):
    """AC3858/51."""


class PhilipsAC385886(PhilipsAC385x51):
    """AC3858/86."""


class PhilipsAC4236(PhilipsGenericCoAPFan):
    """AC4236."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "AG"},
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SLEEP_ALLERGY: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "AS",
            PhilipsApi.SPEED: "as",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "S",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "T",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]
    AVAILABLE_SELECTS = [PhilipsApi.PREFERRED_INDEX]


class PhilipsAC4558(PhilipsGenericCoAPFan):
    """AC4558."""

    AVAILABLE_PRESET_MODES = {
        # there doesn't seem to be a manual mode, so no speed setting as part of preset
        PresetMode.AUTO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "AG",
            PhilipsApi.SPEED: "a",
        },
        PresetMode.GAS: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "F",
            PhilipsApi.SPEED: "a",
        },
        # it seems that when setting the pollution and allergen modes, we also need to set speed "a"
        PresetMode.POLLUTION: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "P",
            PhilipsApi.SPEED: "a",
        },
        PresetMode.ALLERGEN: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "A",
            PhilipsApi.SPEED: "a",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {PhilipsApi.POWER: "1", PhilipsApi.SPEED: "s"},
        PresetMode.SPEED_1: {PhilipsApi.POWER: "1", PhilipsApi.SPEED: "1"},
        PresetMode.SPEED_2: {PhilipsApi.POWER: "1", PhilipsApi.SPEED: "2"},
        PresetMode.TURBO: {PhilipsApi.POWER: "1", PhilipsApi.SPEED: "t"},
    }
    AVAILABLE_SELECTS = [PhilipsApi.PREFERRED_INDEX]
    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]


class PhilipsAC4550(PhilipsAC4558):
    """AC4550."""


class PhilipsAC5659(PhilipsGenericCoAPFan):
    """AC5659."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "P"},
        PresetMode.ALLERGEN: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "A"},
        PresetMode.BACTERIA: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "B"},
        # make speeds available as preset
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "s",
        },
        PresetMode.SPEED_1: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "1",
        },
        PresetMode.SPEED_2: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "2",
        },
        PresetMode.SPEED_3: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "3",
        },
        PresetMode.TURBO: {
            PhilipsApi.POWER: "1",
            PhilipsApi.MODE: "M",
            PhilipsApi.SPEED: "t",
        },
    }
    AVAILABLE_SELECTS = [PhilipsApi.PREFERRED_INDEX]


class PhilipsAMFxxx(PhilipsNew2GenericCoAPFan):
    """AMF family."""

    # REPLACE_PRESET = [PhilipsApi.NEW2_MODE_B, PhilipsApi.NEW2_FAN_SPEED]
    AVAILABLE_PRESET_MODES = {
        # PresetMode.AUTO_PLUS: {
        #     PhilipsApi.NEW2_POWER: 1,
        #     PhilipsApi.NEW2_MODE_B: 0,
        #     PhilipsApi.NEW2_AUTO_PLUS_AI: 1,
        #     # PhilipsApi.NEW2_MODE_C: 3,
        # },
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
            # PhilipsApi.NEW2_AUTO_PLUS_AI: 0,
            # PhilipsApi.NEW2_MODE_C: 3,
        },
        PresetMode.SLEEP: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 17,
            # PhilipsApi.NEW2_MODE_C: 1,
        },
        PresetMode.TURBO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 18,
            # PhilipsApi.NEW2_MODE_C: 18,
        },
    }
    # REPLACE_SPEED = [PhilipsApi.NEW2_MODE_B, PhilipsApi.NEW2_FAN_SPEED]
    AVAILABLE_SPEEDS = {
        PresetMode.SPEED_1: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 1,
            # PhilipsApi.NEW2_MODE_C: 1,
        },
        PresetMode.SPEED_2: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 2,
            # PhilipsApi.NEW2_MODE_C: 2,
        },
        PresetMode.SPEED_3: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 3,
            # PhilipsApi.NEW2_MODE_C: 3,
        },
        PresetMode.SPEED_4: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 4,
            # PhilipsApi.NEW2_MODE_C: 4,
        },
        PresetMode.SPEED_5: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 5,
            # PhilipsApi.NEW2_MODE_C: 5,
        },
        PresetMode.SPEED_6: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 6,
            # PhilipsApi.NEW2_MODE_C: 6,
        },
        PresetMode.SPEED_7: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 7,
            # PhilipsApi.NEW2_MODE_C: 7,
        },
        PresetMode.SPEED_8: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 8,
            # PhilipsApi.NEW2_MODE_C: 8,
        },
        PresetMode.SPEED_9: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 9,
            # PhilipsApi.NEW2_MODE_C: 9,
        },
        PresetMode.SPEED_10: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 10,
            # PhilipsApi.NEW2_MODE_C: 10,
        },
        # PresetMode.TURBO: {
        #     PhilipsApi.NEW2_POWER: 1,
        #     PhilipsApi.NEW2_MODE_B: 18,
        # },
    }

    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT]
    AVAILABLE_SWITCHES = [
        PhilipsApi.NEW2_CHILD_LOCK,
        PhilipsApi.NEW2_BEEP,
        PhilipsApi.NEW2_STANDBY_SENSORS,
        PhilipsApi.NEW2_AUTO_PLUS_AI,
    ]
    AVAILABLE_SELECTS = [PhilipsApi.NEW2_TIMER]
    AVAILABLE_NUMBERS = [PhilipsApi.NEW2_OSCILLATION]


class PhilipsAMF765(PhilipsAMFxxx):
    """AMF765."""

    AVAILABLE_SELECTS = [PhilipsApi.NEW2_CIRCULATION]
    UNAVAILABLE_SENSORS = [PhilipsApi.NEW2_GAS]


class PhilipsAMF870(PhilipsAMFxxx):
    """AMF870."""

    AVAILABLE_SELECTS = [
        PhilipsApi.NEW2_GAS_PREFERRED_INDEX,
        PhilipsApi.NEW2_HEATING,
    ]
    AVAILABLE_NUMBERS = [PhilipsApi.NEW2_TARGET_TEMP]


class PhilipsCX5120(PhilipsNew2GenericCoAPFan):
    """CX5120."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.HIGH: {
            PhilipsApi.POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 65,
        },
        PresetMode.LOW: {
            PhilipsApi.POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 66,
        },
        PresetMode.VENTILATION: {
            PhilipsApi.POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: -127,
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.HIGH: {
            PhilipsApi.POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 65,
        },
        PresetMode.LOW: {
            PhilipsApi.POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 66,
        },
    }
    KEY_OSCILLATION = {
        PhilipsApi.NEW2_OSCILLATION: PhilipsApi.OSCILLATION_MAP,
    }

    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT2]
    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_BEEP]
    UNAVAILABLE_SENSORS = [PhilipsApi.NEW2_FAN_SPEED, PhilipsApi.NEW2_GAS]
    AVAILABLE_SELECTS = [PhilipsApi.NEW2_TIMER2]
    AVAILABLE_NUMBERS = [PhilipsApi.NEW2_TARGET_TEMP]


model_to_class = {
    FanModel.AC0850: PhilipsAC0850,
    FanModel.AC1214: PhilipsAC1214,
    FanModel.AC1715: PhilipsAC1715,
    FanModel.AC2729: PhilipsAC2729,
    FanModel.AC2889: PhilipsAC2889,
    FanModel.AC2936: PhilipsAC2936,
    FanModel.AC2939: PhilipsAC2939,
    FanModel.AC2958: PhilipsAC2958,
    FanModel.AC2959: PhilipsAC2959,
    FanModel.AC3033: PhilipsAC3033,
    FanModel.AC3036: PhilipsAC3036,
    FanModel.AC3039: PhilipsAC3039,
    FanModel.AC3055: PhilipsAC3055,
    FanModel.AC3059: PhilipsAC3059,
    FanModel.AC3259: PhilipsAC3259,
    FanModel.AC3737: PhilipsAC3737,
    FanModel.AC3829: PhilipsAC3829,
    FanModel.AC3836: PhilipsAC3836,
    FanModel.AC3854_50: PhilipsAC385450,
    FanModel.AC3854_51: PhilipsAC385451,
    FanModel.AC3858_50: PhilipsAC385850,
    FanModel.AC3858_51: PhilipsAC385851,
    FanModel.AC3858_86: PhilipsAC385886,
    FanModel.AC4236: PhilipsAC4236,
    FanModel.AC4550: PhilipsAC4550,
    FanModel.AC4558: PhilipsAC4558,
    FanModel.AC5659: PhilipsAC5659,
    FanModel.AMF765: PhilipsAMF765,
    FanModel.AMF870: PhilipsAMF870,
    FanModel.CX5120: PhilipsCX5120,
}
