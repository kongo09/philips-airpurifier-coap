from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

import logging
import asyncio
from asyncio.tasks import Task
from datetime import timedelta

from aioairctrl import CoAPClient

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.entity import Entity
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady

from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)

from .const import *
from .timer import Timer

_LOGGER = logging.getLogger(__name__)

MISSED_PACKAGE_COUNT = 3


class Coordinator:
    def __init__(self, client: CoAPClient, host: str) -> None:
        self.client = client
        self._host = host

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
        _LOGGER.debug(f"init: Creating and autostarting timer for host {self._host}")
        self._timer_disconnected = Timer(
            timeout=self._timeout * MISSED_PACKAGE_COUNT,
            callback=self.reconnect,
            autostart=True,
        )
        self._timer_disconnected._auto_restart = True
        _LOGGER.debug(f"init: finished for host {self._host}")

    async def shutdown(self):
        _LOGGER.debug(f"shutdown: called for host {self._host}")
        if self._reconnect_task is not None:
            _LOGGER.debug(f"shutdown: cancelling reconnect task for host {self._host}")
            self._reconnect_task.cancel()
        if self._timer_disconnected is not None:
            _LOGGER.debug(f"shutdown: cancelling timeout task for host {self._host}")
            self._timer_disconnected._cancel()
        if self.client is not None:
            await self.client.shutdown()

    async def reconnect(self):
        _LOGGER.debug(f"reconnect: called for host {self._host}")
        try:
            if self._reconnect_task is not None:
                # Reconnect stuck
                _LOGGER.debug(
                    f"reconnect: cancelling reconnect task for host {self._host}"
                )
                self._reconnect_task.cancel()
                self._reconnect_task = None
            # Reconnect in new Task, keep timer watching
            _LOGGER.debug(
                f"reconnect: creating new reconnect task for host {self._host}"
            )
            self._reconnect_task = asyncio.create_task(self._reconnect())
        except:
            _LOGGER.exception("Exception on starting reconnect!")

    async def _reconnect(self):
        try:
            _LOGGER.debug("Reconnecting...")
            try:
                await self.client.shutdown()
            except:
                pass
            self.client = await CoAPClient.create(self._host)
            self._start_observing()
        except asyncio.CancelledError:
            # Silently drop this exception, because we are responsible for it.
            # Reconnect took to long
            pass
        except:
            _LOGGER.exception("_reconnect error")

    async def async_first_refresh(self) -> None:
        _LOGGER.debug("async_first_refresh for host %s", self._host)
        try:
            self.status, timeout = await self.client.get_status()
            self._timeout = timeout
            if self._timer_disconnected is not None:
                self._timer_disconnected.setTimeout(timeout * MISSED_PACKAGE_COUNT)
            _LOGGER.debug("finished first refresh for host %s", self._host)
        except Exception as ex:
            _LOGGER.error(
                "config not ready, first refresh failed for host %s", self._host
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
    def __init__(self, coordinator: Coordinator) -> None:
        super().__init__()
        _LOGGER.debug("PhilipsEntity __init__ called")
        _LOGGER.debug(f"coordinator.status is: {coordinator.status}")
        self.coordinator = coordinator
        self._serialNumber = coordinator.status[PHILIPS_DEVICE_ID]
        # self._name = coordinator.status["name"]
        self._name = list(
            filter(None, map(coordinator.status.get, [PHILIPS_NAME, PHILIPS_NEW_NAME]))
        )[0]
        # self._modelName = coordinator.status["modelid"]
        self._modelName = list(
            filter(
                None,
                map(coordinator.status.get, [PHILIPS_MODEL_ID, PHILIPS_NEW_MODEL_ID]),
            )
        )[0]
        self._firmware = coordinator.status["WifiVersion"]
        self._manufacturer = "Philips"

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._serialNumber)},
            "name": self._name,
            "model": self._modelName,
            "manufacturer": self._manufacturer,
            "sw_version": self._firmware,
        }

    @property
    def available(self):
        return self.coordinator.status is not None

    @property
    def _device_status(self) -> dict[str, Any]:
        return self.coordinator.status

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class PhilipsGenericFan(PhilipsEntity, FanEntity):
    def __init__(
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
        return self._unique_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def icon(self) -> str:
        return self._icon


class PhilipsGenericCoAPFanBase(PhilipsGenericFan):
    AVAILABLE_PRESET_MODES = {}
    AVAILABLE_SPEEDS = {}
    AVAILABLE_ATTRIBUTES = []
    AVAILABLE_SWITCHES = []
    AVAILABLE_LIGHTS = []

    KEY_PHILIPS_POWER = PHILIPS_POWER
    STATE_POWER_ON = "1"
    STATE_POWER_OFF = "0"

    def __init__(
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
            device_id = self._device_status[PHILIPS_DEVICE_ID]
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
        status = self._device_status.get(self.KEY_PHILIPS_POWER)
        # _LOGGER.debug("is_on: status=%s - test=%s", status, self.STATE_POWER_ON)
        return status == self.STATE_POWER_ON

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ):
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
        await self.coordinator.client.set_control_value(
            self.KEY_PHILIPS_POWER, self.STATE_POWER_OFF
        )

    @property
    def supported_features(self) -> int:
        features = SUPPORT_PRESET_MODE
        if self._speeds:
            features |= SUPPORT_SET_SPEED
        return features

    @property
    def preset_modes(self) -> Optional[List[str]]:
        return self._preset_modes

    @property
    def preset_mode(self) -> Optional[str]:
        for preset_mode, status_pattern in self._available_preset_modes.items():
            for k, v in status_pattern.items():
                if self._device_status.get(k) != v:
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
        return len(self._speeds)

    @property
    def percentage(self) -> Optional[int]:
        for speed, status_pattern in self._available_speeds.items():
            for k, v in status_pattern.items():
                if self._device_status.get(k) != v:
                    break
            else:
                return ordered_list_item_to_percentage(self._speeds, speed)

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
        else:
            speed = percentage_to_ordered_list_item(self._speeds, percentage)
            status_pattern = self._available_speeds.get(speed)
            if status_pattern:
                await self.coordinator.client.set_control_values(data=status_pattern)

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        def append(
            attributes: dict,
            key: str,
            philips_key: str,
            value_map: Union[dict, Callable[[Any, Any], Any]] = None,
        ):
            if philips_key in self._device_status:
                value = self._device_status[philips_key]
                if isinstance(value_map, dict) and value in value_map:
                    value = value_map.get(value, "unknown")
                elif callable(value_map):
                    value = value_map(value, self._device_status)
                attributes.update({key: value})

        device_attributes = dict()
        for key, philips_key, *rest in self._available_attributes:
            value_map = rest[0] if len(rest) else None
            append(device_attributes, key, philips_key, value_map)
        return device_attributes

    @property
    def icon(self) -> str:
        if not self.is_on:
            return ICON.POWER_BUTTON

        preset_mode = self.preset_mode
        if preset_mode == None:
            return ICON.FAN_SPEED_BUTTON
        if preset_mode in PRESET_MODE_ICON_MAP:
            return PRESET_MODE_ICON_MAP[preset_mode]

        return ICON.FAN_SPEED_BUTTON


class PhilipsGenericCoAPFan(PhilipsGenericCoAPFanBase):
    AVAILABLE_PRESET_MODES = {}
    AVAILABLE_SPEEDS = {}

    AVAILABLE_ATTRIBUTES = [
        # device information
        (ATTR_NAME, PHILIPS_NAME),
        (ATTR_TYPE, PHILIPS_TYPE),
        (ATTR_MODEL_ID, PHILIPS_MODEL_ID),
        (ATTR_PRODUCT_ID, PHILIPS_PRODUCT_ID),
        (ATTR_DEVICE_ID, PHILIPS_DEVICE_ID),
        (ATTR_DEVICE_VERSION, PHILIPS_DEVICE_VERSION),
        (ATTR_SOFTWARE_VERSION, PHILIPS_SOFTWARE_VERSION),
        (ATTR_WIFI_VERSION, PHILIPS_WIFI_VERSION),
        (ATTR_ERROR_CODE, PHILIPS_ERROR_CODE),
        (ATTR_ERROR, PHILIPS_ERROR_CODE, PHILIPS_ERROR_CODE_MAP),
        # device configuration
        (ATTR_LANGUAGE, PHILIPS_LANGUAGE),
        (ATTR_PREFERRED_INDEX, PHILIPS_PREFERRED_INDEX, PHILIPS_PREFERRED_INDEX_MAP),
        # device sensors
        (
            ATTR_RUNTIME,
            PHILIPS_RUNTIME,
            lambda x, _: str(timedelta(seconds=round(x / 1000))),
        ),
    ]

    AVAILABLE_LIGHTS = [PHILIPS_DISPLAY_BACKLIGHT, PHILIPS_LIGHT_BRIGHTNESS]

    AVAILABLE_SWITCHES = []
    AVAILABLE_SELECTS = []


class PhilipsNewGenericCoAPFan(PhilipsGenericCoAPFanBase):
    AVAILABLE_PRESET_MODES = {}
    AVAILABLE_SPEEDS = {}

    AVAILABLE_ATTRIBUTES = [
        # device information
        (ATTR_NAME, PHILIPS_NEW_NAME),
        (ATTR_MODEL_ID, PHILIPS_NEW_MODEL_ID),
        (ATTR_PRODUCT_ID, PHILIPS_PRODUCT_ID),
        (ATTR_DEVICE_ID, PHILIPS_DEVICE_ID),
        (ATTR_SOFTWARE_VERSION, PHILIPS_SOFTWARE_VERSION),
        (ATTR_WIFI_VERSION, PHILIPS_WIFI_VERSION),
        # (ATTR_ERROR_CODE, PHILIPS_ERROR_CODE),
        # (ATTR_ERROR, PHILIPS_ERROR_CODE, PHILIPS_ERROR_CODE_MAP),
        # device configuration
        (ATTR_LANGUAGE, PHILIPS_NEW_LANGUAGE),
        (
            ATTR_PREFERRED_INDEX,
            PHILIPS_NEW_PREFERRED_INDEX,
            PHILIPS_PREFERRED_INDEX_MAP,
        ),
        # device sensors
        (
            ATTR_RUNTIME,
            PHILIPS_RUNTIME,
            lambda x, _: str(timedelta(seconds=round(x / 1000))),
        ),
    ]

    AVAILABLE_LIGHTS = []
    AVAILABLE_SWITCHES = []
    AVAILABLE_SELECTS = []
    UNAVAILABLE_FILTERS = [PHILIPS_FILTER_NANOPROTECT_PREFILTER]

    KEY_PHILIPS_POWER = PHILIPS_NEW_POWER
    STATE_POWER_ON = "ON"
    STATE_POWER_OFF = "OFF"


class PhilipsHumidifierMixin(PhilipsGenericCoAPFanBase):
    AVAILABLE_SELECTS = [PHILIPS_FUNCTION, PHILIPS_HUMIDITY_TARGET]


# similar to the AC1715, the AC0850 seems to be a new class of devices that
# follows some patterns of its own
class PhilipsAC0850(PhilipsNewGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Auto General"},
        PRESET_MODE_TURBO: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Turbo"},
        PRESET_MODE_SLEEP: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Sleep"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Sleep"},
        PRESET_MODE_TURBO: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Turbo"},
    }


# the AC1715 seems to be a new class of devices that follows some patterns of its own
class PhilipsAC1715(PhilipsNewGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Auto General"},
        SPEED_1: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Gentle/Speed 1"},
        SPEED_2: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Speed 2"},
        PRESET_MODE_TURBO: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Turbo"},
        PRESET_MODE_SLEEP: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Sleep"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Sleep"},
        SPEED_1: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Gentle/Speed 1"},
        SPEED_2: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Speed 2"},
        PRESET_MODE_TURBO: {PHILIPS_NEW_POWER: "ON", PHILIPS_NEW_MODE: "Turbo"},
    }
    AVAILABLE_LIGHTS = [PHILIPS_NEW_DISPLAY_BACKLIGHT]


# TODO consolidate these classes as soon as we see a proper pattern


class PhilipsAC1214(PhilipsGenericCoAPFan):
    # the AC1214 doesn't seem to like a power on call when the mode or speed is set,
    # so this needs to be handled separately
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_MODE: "P"},
        PRESET_MODE_ALLERGEN: {PHILIPS_MODE: "A"},
        # make speeds available as preset
        PRESET_MODE_NIGHT: {PHILIPS_MODE: "N"},
        SPEED_1: {PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_NIGHT: {PHILIPS_MODE: "N"},
        SPEED_1: {PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SWITCHES = [PHILIPS_CHILD_LOCK]

    async def async_set_a(self) -> None:
        _LOGGER.debug(f"AC1214 switches to mode 'A' first")
        a_status_pattern = self._available_preset_modes.get(PRESET_MODE_ALLERGEN)
        await self.coordinator.client.set_control_values(data=a_status_pattern)
        await asyncio.sleep(1)
        return

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug(f"AC1214 async_set_preset_mode is called with: {preset_mode}")

        # the AC1214 doesn't like it if we set a preset mode to switch on the device,
        # so it needs to be done in sequence
        if not self.is_on:
            _LOGGER.debug(f"AC1214 is switched on without setting a mode")
            await self.coordinator.client.set_control_value(
                PHILIPS_POWER, PHILIPS_POWER_MAP[SWITCH_ON]
            )
            await asyncio.sleep(1)

        # the AC1214 also doesn't seem to like switching to mode 'M' without cycling through mode 'A'
        current_pattern = self._available_preset_modes.get(self.preset_mode)
        _LOGGER.debug(f"AC1214 is currently on mode: {current_pattern}")
        if preset_mode:
            _LOGGER.debug(f"AC1214 preset mode requested: {preset_mode}")
            status_pattern = self._available_preset_modes.get(preset_mode)
            _LOGGER.debug(f"this corresponds to status pattern: {status_pattern}")
            if (
                status_pattern
                and status_pattern.get(PHILIPS_MODE) != "A"
                and current_pattern.get(PHILIPS_MODE) != "M"
            ):
                await self.async_set_a()
            _LOGGER.debug(f"AC1214 sets preset mode to: {preset_mode}")
            if status_pattern:
                await self.coordinator.client.set_control_values(data=status_pattern)
        return

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug(f"AC1214 async_set_percentage is called with: {percentage}")

        # the AC1214 doesn't like it if we set a preset mode to switch on the device,
        # so it needs to be done in sequence
        if not self.is_on:
            _LOGGER.debug(f"AC1214 is switched on without setting a mode")
            await self.coordinator.client.set_control_value(
                PHILIPS_POWER, PHILIPS_POWER_MAP[SWITCH_ON]
            )
            await asyncio.sleep(1)

        current_pattern = self._available_preset_modes.get(self.preset_mode)
        _LOGGER.debug(f"AC1214 is currently on mode: {current_pattern}")
        if percentage == 0:
            _LOGGER.debug(f"AC1214 uses 0% to switch off")
            await self.async_turn_off()
        else:
            # the AC1214 also doesn't seem to like switching to mode 'M' without cycling through mode 'A'
            _LOGGER.debug(f"AC1214 speed change requested: {percentage}")
            speed = percentage_to_ordered_list_item(self._speeds, percentage)
            status_pattern = self._available_speeds.get(speed)
            _LOGGER.debug(f"this corresponds to status pattern: {status_pattern}")
            if (
                status_pattern
                and status_pattern.get(PHILIPS_MODE) != "A"
                and current_pattern.get(PHILIPS_MODE) != "M"
            ):
                await self.async_set_a()
            _LOGGER.debug(f"AC1214 sets speed percentage to: {percentage}")
            if status_pattern:
                await self.coordinator.client.set_control_values(data=status_pattern)
        return

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ):
        _LOGGER.debug(
            f"AC1214 async_turn_on called with percentage={percentage} and preset_mode={preset_mode}"
        )
        # the AC1214 doesn't like it if we set a preset mode to switch on the device,
        # so it needs to be done in sequence
        if not self.is_on:
            _LOGGER.debug(f"AC1214 is switched on without setting a mode")
            await self.coordinator.client.set_control_value(
                PHILIPS_POWER, PHILIPS_POWER_MAP[SWITCH_ON]
            )
            await asyncio.sleep(1)

        if preset_mode:
            _LOGGER.debug(f"AC1214 preset mode requested: {preset_mode}")
            await self.async_set_preset_mode(preset_mode)
            return
        if percentage:
            _LOGGER.debug(f"AC1214 speed change requested: {percentage}")
            await self.async_set_percentage(percentage)
            return


class PhilipsAC2729(
    PhilipsHumidifierMixin,
    PhilipsGenericCoAPFan,
):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "P"},
        PRESET_MODE_ALLERGEN: {PHILIPS_POWER: "1", PHILIPS_MODE: "A"},
        # make speeds available as preset
        PRESET_MODE_NIGHT: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_NIGHT: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SWITCHES = [PHILIPS_CHILD_LOCK]


class PhilipsAC2889(PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "P"},
        PRESET_MODE_ALLERGEN: {PHILIPS_POWER: "1", PHILIPS_MODE: "A"},
        PRESET_MODE_BACTERIA: {PHILIPS_POWER: "1", PHILIPS_MODE: "B"},
        # make speeds available as preset
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }


class PhilipsAC29xx(PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "AG"},
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S"},
        PRESET_MODE_GENTLE: {PHILIPS_POWER: "1", PHILIPS_MODE: "GT"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S"},
        PRESET_MODE_GENTLE: {PHILIPS_POWER: "1", PHILIPS_MODE: "GT"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T"},
    }


class PhilipsAC2936(PhilipsAC29xx):
    pass


class PhilipsAC2939(PhilipsAC29xx):
    pass


class PhilipsAC2958(PhilipsAC29xx):
    pass

class PhilipsAC2959(PhilipsAC29xx):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "AG"},
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S"},
        PRESET_MODE_GENTLE: {PHILIPS_POWER: "1", PHILIPS_MODE: "GT"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S"},
        PRESET_MODE_GENTLE: {PHILIPS_POWER: "1", PHILIPS_MODE: "GT"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T"},
    }
    AVAILABLE_SWITCHES = [PHILIPS_CHILD_LOCK]
    AVAILABLE_SELECTS = [PHILIPS_PREFERRED_INDEX]


class PhilipsAC30xx(PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "AG"},
        # make speeds available as preset
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T", PHILIPS_SPEED: "t"},
    }


class PhilipsAC3033(PhilipsAC30xx):
    pass


class PhilipsAC3036(PhilipsAC30xx):
    pass


class PhilipsAC3039(PhilipsAC30xx):
    pass


class PhilipsAC3055(PhilipsAC30xx):
    pass


class PhilipsAC3059(PhilipsAC30xx):
    pass


class PhilipsAC3259(PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "P"},
        PRESET_MODE_ALLERGEN: {PHILIPS_POWER: "1", PHILIPS_MODE: "A"},
        PRESET_MODE_BACTERIA: {PHILIPS_POWER: "1", PHILIPS_MODE: "B"},
        # make speeds available as preset
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }


class PhilipsAC3829(PhilipsHumidifierMixin, PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "P"},
        PRESET_MODE_ALLERGEN: {PHILIPS_POWER: "1", PHILIPS_MODE: "A"},
        # make speeds available as preset
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SWITCHES = [PHILIPS_CHILD_LOCK]


class PhilipsAC385x50(PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "AG"},
        # make speeds available as preset
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T", PHILIPS_SPEED: "t"},
    }


class PhilipsAC385450(PhilipsAC385x50):
    pass


class PhilipsAC385850(PhilipsAC385x50):
    pass


class PhilipsAC385x51(PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "AG"},
        # make speeds available as preset
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        PRESET_MODE_SLEEP_ALLERGY: {
            PHILIPS_POWER: "1",
            PHILIPS_MODE: "AS",
            PHILIPS_SPEED: "as",
        },
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SWITCHES = [PHILIPS_CHILD_LOCK]


class PhilipsAC385451(PhilipsAC385x51):
    pass


class PhilipsAC385851(PhilipsAC385x51):
    pass


class PhilipsAC4236(PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "AG"},
        # make speeds available as preset
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "S", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "T", PHILIPS_SPEED: "t"},
    }


class PhilipsAC4558(PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        # there doesn't seem to be a manual mode, so no speed setting as part of preset
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "AG"},
        PRESET_MODE_GAS: {PHILIPS_POWER: "1", PHILIPS_MODE: "F"},
        # it seems that when setting the pollution and allergen modes, we also need to set speed "a"
        PRESET_MODE_POLLUTION: {
            PHILIPS_POWER: "1",
            PHILIPS_MODE: "P",
            PHILIPS_SPEED: "a",
        },
        PRESET_MODE_ALLERGEN: {
            PHILIPS_POWER: "1",
            PHILIPS_MODE: "A",
            PHILIPS_SPEED: "a",
        },
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_SPEED: "2"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_SPEED: "t"},
    }


class PhilipsAC5659(PhilipsGenericCoAPFan):
    AVAILABLE_PRESET_MODES = {
        PRESET_MODE_AUTO: {PHILIPS_POWER: "1", PHILIPS_MODE: "P"},
        PRESET_MODE_ALLERGEN: {PHILIPS_POWER: "1", PHILIPS_MODE: "A"},
        PRESET_MODE_BACTERIA: {PHILIPS_POWER: "1", PHILIPS_MODE: "B"},
        # make speeds available as preset
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }
    AVAILABLE_SPEEDS = {
        PRESET_MODE_SLEEP: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "s"},
        SPEED_1: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "1"},
        SPEED_2: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "2"},
        SPEED_3: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "3"},
        PRESET_MODE_TURBO: {PHILIPS_POWER: "1", PHILIPS_MODE: "M", PHILIPS_SPEED: "t"},
    }


model_to_class = {
    MODEL_AC0850: PhilipsAC0850,
    MODEL_AC1214: PhilipsAC1214,
    MODEL_AC1715: PhilipsAC1715,
    MODEL_AC2729: PhilipsAC2729,
    MODEL_AC2889: PhilipsAC2889,
    MODEL_AC2936: PhilipsAC2936,
    MODEL_AC2939: PhilipsAC2939,
    MODEL_AC2958: PhilipsAC2958,
    MODEL_AC2959: PhilipsAC2959,
    MODEL_AC3033: PhilipsAC3033,
    MODEL_AC3036: PhilipsAC3036,
    MODEL_AC3039: PhilipsAC3039,
    MODEL_AC3055: PhilipsAC3055,
    MODEL_AC3059: PhilipsAC3059,
    MODEL_AC3259: PhilipsAC3259,
    MODEL_AC3829: PhilipsAC3829,
    MODEL_AC3854_50: PhilipsAC385450,
    MODEL_AC3854_51: PhilipsAC385451,
    MODEL_AC3858_50: PhilipsAC385850,
    MODEL_AC3858_51: PhilipsAC385851,
    MODEL_AC4236: PhilipsAC4236,
    MODEL_AC4558: PhilipsAC4558,
    MODEL_AC5659: PhilipsAC5659,
}
