"""Collection of classes to manage Philips AirPurifier devices."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .config_entry_data import ConfigEntryData
from .const import (
    DOMAIN,
    ICON,
    MANUFACTURER,
    SWITCH_OFF,
    SWITCH_ON,
    FanAttributes,
    FanModel,
    PhilipsApi,
    PresetMode,
)

_LOGGER = logging.getLogger(__name__)


class PhilipsEntity(Entity):
    """Class to represent a generic Philips entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config_entry_data: ConfigEntryData,
    ) -> None:
        """Initialize the PhilipsEntity."""

        super().__init__()

        self.hass = hass
        self.config_entry = entry
        self.config_entry_data = config_entry_data
        self.coordinator = self.config_entry_data.coordinator
        name = self.config_entry_data.device_information.name

        self._attr_device_info = DeviceInfo(
            name=name,
            manufacturer=MANUFACTURER,
            model=list(
                filter(
                    None,
                    map(
                        self._device_status.get,
                        [
                            PhilipsApi.MODEL_ID,
                            PhilipsApi.NEW_MODEL_ID,
                            PhilipsApi.NEW2_MODEL_ID,
                        ],
                    ),
                )
            )[0],
            sw_version=self._device_status["WifiVersion"],
            serial_number=self._device_status[PhilipsApi.DEVICE_ID],
            identifiers={(DOMAIN, self._device_status[PhilipsApi.DEVICE_ID])},
            connections={
                (CONNECTION_NETWORK_MAC, self.config_entry_data.device_information.mac)
            }
            if self.config_entry_data.device_information.mac is not None
            else None,
        )

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

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

        remove_callback = self.coordinator.async_add_listener(
            self._handle_coordinator_update
        )

        self.async_on_remove(remove_callback)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.config_entry_data.latest_status = self._device_status
        self.async_write_ha_state()


class PhilipsGenericControlBase(PhilipsEntity):
    """Class as basis for control entities of a Philips device."""

    AVAILABLE_ATTRIBUTES = []
    AVAILABLE_PRESET_MODES = {}
    REPLACE_PRESET = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config_entry_data: ConfigEntryData,
    ) -> None:
        """Initialize the PhilipsGenericControlBase."""

        super().__init__(hass, entry, config_entry_data)

        self._available_attributes = []
        self._collect_available_attributes()

        self._preset_modes = []
        self._available_preset_modes = {}
        self._collect_available_preset_modes()

    def _collect_available_attributes(self):
        attributes = []

        for cls in reversed(self.__class__.__mro__):
            cls_attributes = getattr(cls, "AVAILABLE_ATTRIBUTES", [])
            attributes.extend(cls_attributes)

        self._available_attributes = attributes

    def _collect_available_preset_modes(self):
        preset_modes = {}

        for cls in reversed(self.__class__.__mro__):
            cls_preset_modes = getattr(cls, "AVAILABLE_PRESET_MODES", {})
            preset_modes.update(cls_preset_modes)

        self._available_preset_modes = preset_modes
        self._preset_modes = list(self._available_preset_modes.keys())

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the extra state attributes."""

        def append(
            attributes: dict,
            key: str,
            philips_key: str,
            value_map: dict | Callable[[Any, Any], Any] | None = None,
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


class PhilipsGenericFanBase(PhilipsGenericControlBase, FanEntity):
    """Class as basis to manage a generic Philips fan."""

    AVAILABLE_SPEEDS = {}
    REPLACE_SPEED = None
    AVAILABLE_SWITCHES = []
    AVAILABLE_LIGHTS = []
    AVAILABLE_NUMBERS = []
    AVAILABLE_BINARY_SENSORS = []

    KEY_PHILIPS_POWER = PhilipsApi.POWER
    STATE_POWER_ON = "1"
    STATE_POWER_OFF = "0"

    KEY_OSCILLATION = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config_entry_data: ConfigEntryData,
    ) -> None:
        """Initialize the PhilipsGenericFanBase."""

        super().__init__(hass, entry, config_entry_data)

        self._attr_name = list(
            filter(
                None,
                map(
                    self._device_status.get,
                    [
                        PhilipsApi.NAME,
                        PhilipsApi.NEW_NAME,
                        PhilipsApi.NEW2_NAME,
                    ],
                ),
            )
        )[0]
        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}"

        self._speeds = []
        self._available_speeds = {}
        self._collect_available_speeds()

        # set the supported features of the fan
        self._attr_supported_features |= (
            FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

        if self.KEY_OSCILLATION is not None:
            self._attr_supported_features |= FanEntityFeature.OSCILLATE

    def _collect_available_speeds(self):
        speeds = {}

        for cls in reversed(self.__class__.__mro__):
            cls_speeds = getattr(cls, "AVAILABLE_SPEEDS", {})
            speeds.update(cls_speeds)

        self._available_speeds = speeds
        self._speeds = list(self._available_speeds.keys())

        if len(self._speeds) > 0:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED

    @property
    def is_on(self) -> bool:
        """Return if the fan is on."""
        status = self._device_status.get(self.KEY_PHILIPS_POWER)
        return status == self.STATE_POWER_ON

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
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

        self._device_status[self.KEY_PHILIPS_POWER] = self.STATE_POWER_ON
        self._handle_coordinator_update()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        await self.coordinator.client.set_control_value(
            self.KEY_PHILIPS_POWER, self.STATE_POWER_OFF
        )

        self._device_status[self.KEY_PHILIPS_POWER] = self.STATE_POWER_OFF
        self._handle_coordinator_update()

    @property
    def preset_modes(self) -> list[str] | None:
        """Return the supported preset modes."""
        # the fan uses the preset modes as collected from the classes
        return self._preset_modes

    @property
    def preset_mode(self) -> str | None:
        """Return the selected preset mode."""
        # the fan uses the preset modes as collected from the classes

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

        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        # the fan uses the preset modes as collected from the classes

        status_pattern = self._available_preset_modes.get(preset_mode)
        if status_pattern:
            await self.coordinator.client.set_control_values(data=status_pattern)
            self._device_status.update(status_pattern)
            self._handle_coordinator_update()

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

        if status is None:
            return None

        if isinstance(on, int):
            return status == on

        if isinstance(on, list):
            return status in on

        return None

    async def async_oscillate(self, oscillating: bool) -> None:
        """Osciallate the fan."""

        if self.KEY_OSCILLATION is None:
            return

        key = next(iter(self.KEY_OSCILLATION))
        values = self.KEY_OSCILLATION.get(key)
        on = values.get(SWITCH_ON)
        off = values.get(SWITCH_OFF)

        on_value = on if isinstance(on, int) else on[0]

        if oscillating:
            await self.coordinator.client.set_control_value(key, on_value)
        else:
            await self.coordinator.client.set_control_value(key, off)

        self._device_status[key] = on_value if oscillating else off
        self._handle_coordinator_update()

    @property
    def percentage(self) -> int | None:
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

            self._device_status.update(status_pattern)
            self._handle_coordinator_update()

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


class PhilipsGenericFan(PhilipsGenericFanBase):
    """Class to manage a generic Philips fan."""

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


class PhilipsNewGenericFan(PhilipsGenericFanBase):
    """Class to manage a new generic fan."""

    AVAILABLE_ATTRIBUTES = [
        # device information
        (FanAttributes.NAME, PhilipsApi.NEW_NAME),
        (FanAttributes.MODEL_ID, PhilipsApi.NEW_MODEL_ID),
        (FanAttributes.PRODUCT_ID, PhilipsApi.PRODUCT_ID),
        (FanAttributes.DEVICE_ID, PhilipsApi.DEVICE_ID),
        (FanAttributes.SOFTWARE_VERSION, PhilipsApi.NEW_SOFTWARE_VERSION),
        (FanAttributes.WIFI_VERSION, PhilipsApi.WIFI_VERSION),
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


class PhilipsNew2GenericFan(PhilipsGenericFanBase):
    """Class to manage another new generic fan."""

    AVAILABLE_ATTRIBUTES = [
        # device information
        (FanAttributes.NAME, PhilipsApi.NEW2_NAME),
        (FanAttributes.MODEL_ID, PhilipsApi.NEW2_MODEL_ID),
        (FanAttributes.PRODUCT_ID, PhilipsApi.PRODUCT_ID),
        (FanAttributes.DEVICE_ID, PhilipsApi.DEVICE_ID),
        (FanAttributes.SOFTWARE_VERSION, PhilipsApi.NEW2_SOFTWARE_VERSION),
        (FanAttributes.WIFI_VERSION, PhilipsApi.WIFI_VERSION),
        (FanAttributes.ERROR_CODE, PhilipsApi.NEW2_ERROR_CODE),
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


# similar to the AC1715, the AC0850 seems to be a new class of devices that
# follows some patterns of its own


# the AC0850/11 comes in two versions.
# the first version has a Wifi string starting with "AWS_Philips_AIR"
# the second version has a Wifi string starting with "AWS_Philips_AIR_Combo"
class PhilipsAC085011(PhilipsNewGenericFan):
    """AC0850/11 with firmware AWS_Philips_AIR."""

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


class PhilipsAC085011C(PhilipsNew2GenericFan):
    """AC0850/11 with firmware AWS_Philips_AIR_Combo."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.TURBO: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 18},
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
        PresetMode.TURBO: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 18},
    }
    # the prefilter data is present but doesn't change for this device, so let's take it out
    UNAVAILABLE_FILTERS = [PhilipsApi.FILTER_NANOPROTECT_PREFILTER]


class PhilipsAC085020(PhilipsAC085011):
    """AC0850/20 with firmware AWS_Philips_AIR."""


class PhilipsAC085020C(PhilipsAC085011C):
    """AC0850/20 with firmware AWS_Philips_AIR_Combo."""


class PhilipsAC085031(PhilipsAC085011):
    """AC0850/31."""


class PhilipsAC085081(PhilipsAC085011C):
    """AC0850/81."""


class PhilipsAC085085(PhilipsAC085011):
    """AC0850/85."""


class PhilipsAC0950(PhilipsNew2GenericFan):
    """AC0950."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.TURBO: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 18},
        PresetMode.MEDIUM: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 19},
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
        PresetMode.MEDIUM: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 19},
        PresetMode.TURBO: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 18},
    }
    # the prefilter data is present but doesn't change for this device, so let's take it out
    UNAVAILABLE_FILTERS = [PhilipsApi.FILTER_NANOPROTECT_PREFILTER]

    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_CHILD_LOCK, PhilipsApi.NEW2_BEEP]
    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT3]
    AVAILABLE_SELECTS = [PhilipsApi.NEW2_GAS_PREFERRED_INDEX, PhilipsApi.NEW2_TIMER2]


class PhilipsAC0951(PhilipsAC0950):
    """AC0951."""


# the AC1715 seems to be a new class of devices that follows some patterns of its own
class PhilipsAC1715(PhilipsNewGenericFan):
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


class PhilipsAC1214(PhilipsGenericFan):
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
        percentage: int | None = None,
        preset_mode: str | None = None,
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


class PhilipsAC2729(PhilipsGenericFan):
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
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.HUMIDITY_TARGET]
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.ERROR_CODE]


class PhilipsAC2889(PhilipsGenericFan):
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


class PhilipsAC29xx(PhilipsGenericFan):
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


class PhilipsAC303x(PhilipsGenericFan):
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


class PhilipsAC305x(PhilipsGenericFan):
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


# this device seems similar to the AMF family
class PhilipsAC32xx(PhilipsNew2GenericFan):
    """AC32xx family."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.MEDIUM: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 19,
        },
        PresetMode.TURBO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 18,
        },
        PresetMode.SLEEP: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 17,
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SPEED_1: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 1,
        },
        PresetMode.SPEED_2: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 2,
        },
        PresetMode.SPEED_3: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 3,
        },
        PresetMode.SPEED_4: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 4,
        },
        PresetMode.SPEED_5: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 5,
        },
    }

    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT3]
    AVAILABLE_SWITCHES = [
        PhilipsApi.NEW2_CHILD_LOCK,
        PhilipsApi.NEW2_BEEP,
        PhilipsApi.NEW2_AUTO_PLUS_AI,
    ]
    AVAILABLE_SELECTS = [
        PhilipsApi.NEW2_TIMER2,
        PhilipsApi.NEW2_LAMP_MODE,
        PhilipsApi.NEW2_PREFERRED_INDEX,
    ]


class PhilipsAC3210(PhilipsAC32xx):
    """AC3210."""

    AVAILABLE_SELECTS = [PhilipsApi.NEW_PREFERRED_INDEX]


class PhilipsAC3220(PhilipsAC3210):
    """AC3220."""


class PhilipsAC3221(PhilipsAC3210):
    """AC3221."""


class PhilipsAC3259(PhilipsGenericFan):
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


class PhilipsAC3420(PhilipsAC0950):
    """AC3420."""

    AVAILABLE_SELECTS = [PhilipsApi.NEW2_LAMP_MODE]
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.NEW2_HUMIDITY_TARGET]


class PhilipsAC3421(PhilipsAC3420):
    """AC3421."""


class PhilipsAC3737(PhilipsNew2GenericFan):
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

    # AVAILABLE_SELECTS = [PhilipsApi.NEW2_HUMIDITY_TARGET]
    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT2]
    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_CHILD_LOCK]
    UNAVAILABLE_SENSORS = [PhilipsApi.NEW2_FAN_SPEED]
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.NEW2_ERROR_CODE, PhilipsApi.NEW2_MODE_A]
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.NEW2_HUMIDITY_TARGET]


class PhilipsAC3829(PhilipsGenericFan):
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
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.ERROR_CODE]
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.HUMIDITY_TARGET]


class PhilipsAC3836(PhilipsGenericFan):
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


class PhilipsAC385x50(PhilipsGenericFan):
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


class PhilipsAC385x51(PhilipsGenericFan):
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


class PhilipsAC385883(PhilipsAC385x51):
    """AC3858/83."""


class PhilipsAC385886(PhilipsAC385x51):
    """AC3858/86."""


class PhilipsAC4220(PhilipsAC32xx):
    """AC4220."""

    AVAILABLE_SELECTS = [PhilipsApi.NEW2_GAS_PREFERRED_INDEX]


class PhilipsAC4221(PhilipsAC4220):
    """AC4221."""


class PhilipsAC4236(PhilipsGenericFan):
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


class PhilipsAC4558(PhilipsGenericFan):
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


class PhilipsAC5659(PhilipsGenericFan):
    """AC5659."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.POLLUTION: {PhilipsApi.POWER: "1", PhilipsApi.MODE: "P"},
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


class PhilipsAC5660(PhilipsAC5659):
    """AC5660."""


class PhilipsAMFxxx(PhilipsNew2GenericFan):
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


class PhilipsCX5120(PhilipsNew2GenericFan):
    """CX5120."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.HIGH: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 65,
        },
        PresetMode.LOW: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 66,
        },
        PresetMode.VENTILATION: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: -127,
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.HIGH: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 65,
        },
        PresetMode.LOW: {
            PhilipsApi.NEW2_POWER: 1,
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


class PhilipsCX3550(PhilipsNew2GenericFan):
    """CX3550."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.SPEED_1: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: 1,
            PhilipsApi.NEW2_MODE_C: 1,
        },
        PresetMode.SPEED_2: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: 2,
            PhilipsApi.NEW2_MODE_C: 2,
        },
        PresetMode.SPEED_3: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: 3,
            PhilipsApi.NEW2_MODE_C: 3,
        },
        PresetMode.NATURAL: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: -126,
            PhilipsApi.NEW2_MODE_C: 1,
        },
        PresetMode.SLEEP: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: 17,
            PhilipsApi.NEW2_MODE_C: 2,
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SPEED_1: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: 1,
            PhilipsApi.NEW2_MODE_C: 1,
        },
        PresetMode.SPEED_2: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: 2,
            PhilipsApi.NEW2_MODE_C: 2,
        },
        PresetMode.SPEED_3: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: 3,
            PhilipsApi.NEW2_MODE_C: 3,
        },
    }
    KEY_OSCILLATION = {
        PhilipsApi.NEW2_OSCILLATION: PhilipsApi.OSCILLATION_MAP2,
    }

    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_BEEP]
    AVAILABLE_SELECTS = [PhilipsApi.NEW2_TIMER2]


class PhilipsHU1509(PhilipsNew2GenericFan):
    """HU1509."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.HIGH: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 65},
        PresetMode.MEDIUM: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 19},
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
        PresetMode.MEDIUM: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 19},
        PresetMode.HIGH: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 65},
    }

    AVAILABLE_SWITCHES = [
        PhilipsApi.NEW2_BEEP,
        PhilipsApi.NEW2_STANDBY_SENSORS,
    ]
    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT4]
    AVAILABLE_SELECTS = [
        PhilipsApi.NEW2_TIMER2,
        PhilipsApi.NEW2_LAMP_MODE2,
        PhilipsApi.NEW2_AMBIENT_LIGHT_MODE,
    ]
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.NEW2_ERROR_CODE]
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.NEW2_HUMIDITY_TARGET2]


class PhilipsHU1510(PhilipsHU1509):
    """HU1510."""


class PhilipsHU5710(PhilipsNew2GenericFan):
    """HU5710."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.HIGH: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 65},
        PresetMode.MEDIUM: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 19},
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
        PresetMode.MEDIUM: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 19},
        PresetMode.HIGH: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 65},
    }

    AVAILABLE_SWITCHES = [
        PhilipsApi.NEW2_CHILD_LOCK,
        PhilipsApi.NEW2_BEEP,
        PhilipsApi.NEW2_QUICKDRY_MODE,
        PhilipsApi.NEW2_AUTO_QUICKDRY_MODE,
        PhilipsApi.NEW2_STANDBY_SENSORS,
    ]
    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT4]
    AVAILABLE_SELECTS = [
        PhilipsApi.NEW2_TIMER2,
        PhilipsApi.NEW2_LAMP_MODE2,
        PhilipsApi.NEW2_AMBIENT_LIGHT_MODE,
    ]
    # AVAILABLE_NUMBERS = [PhilipsApi.NEW2_HUMIDITY_TARGET2]
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.NEW2_ERROR_CODE]
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.NEW2_HUMIDITY_TARGET2]


model_to_class = {
    FanModel.AC0850_11: PhilipsAC085011,
    FanModel.AC0850_11C: PhilipsAC085011C,
    FanModel.AC0850_20: PhilipsAC085020,
    FanModel.AC0850_20C: PhilipsAC085020C,
    FanModel.AC0850_31: PhilipsAC085031,
    FanModel.AC0850_81: PhilipsAC085081,
    FanModel.AC0850_85: PhilipsAC085085,
    FanModel.AC0950: PhilipsAC0950,
    FanModel.AC0951: PhilipsAC0951,
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
    FanModel.AC3210: PhilipsAC3210,
    FanModel.AC3220: PhilipsAC3220,
    FanModel.AC3221: PhilipsAC3221,
    FanModel.AC3259: PhilipsAC3259,
    FanModel.AC3420: PhilipsAC3420,
    FanModel.AC3421: PhilipsAC3421,
    FanModel.AC3737: PhilipsAC3737,
    FanModel.AC3829: PhilipsAC3829,
    FanModel.AC3836: PhilipsAC3836,
    FanModel.AC3854_50: PhilipsAC385450,
    FanModel.AC3854_51: PhilipsAC385451,
    FanModel.AC3858_50: PhilipsAC385850,
    FanModel.AC3858_51: PhilipsAC385851,
    FanModel.AC3858_83: PhilipsAC385883,
    FanModel.AC3858_86: PhilipsAC385886,
    FanModel.AC4220: PhilipsAC4220,
    FanModel.AC4221: PhilipsAC4221,
    FanModel.AC4236: PhilipsAC4236,
    FanModel.AC4550: PhilipsAC4550,
    FanModel.AC4558: PhilipsAC4558,
    FanModel.AC5659: PhilipsAC5659,
    FanModel.AC5660: PhilipsAC5660,
    FanModel.AMF765: PhilipsAMF765,
    FanModel.AMF870: PhilipsAMF870,
    FanModel.CX5120: PhilipsCX5120,
    FanModel.CX3550: PhilipsCX3550,
    FanModel.HU1509: PhilipsHU1510,
    FanModel.HU1510: PhilipsHU1510,
    FanModel.HU5710: PhilipsHU5710,
}
