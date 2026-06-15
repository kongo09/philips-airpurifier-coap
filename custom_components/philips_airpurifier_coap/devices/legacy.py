"""Legacy generation Philips AirPurifier devices (PhilipsGenericFan)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.util.percentage import percentage_to_ordered_list_item

from ..const import (
    SWITCH_ON,
    FanAttributes,
    PhilipsApi,
    PresetMode,
)
from .base import PhilipsGenericFanBase

_LOGGER = logging.getLogger(__name__)


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

    async def _ensure_power_on(self) -> None:
        """Ensure device is powered on before mode changes."""
        if not self.is_on:
            _LOGGER.debug("AC1214 is switched on without setting a mode")
            await self.coordinator.client.set_control_value(
                PhilipsApi.POWER, PhilipsApi.POWER_MAP[SWITCH_ON]
            )
            await asyncio.sleep(1)

    async def _ensure_mode_transition(self, target_mode: str) -> None:
        """Ensure proper mode transition through 'A' state if needed."""
        current_pattern = self._available_preset_modes.get(self.preset_mode)
        if target_mode != "A" and current_pattern and current_pattern.get(PhilipsApi.MODE) != "M":
            _LOGGER.debug("AC1214 switches to mode 'A' first")
            a_status_pattern = self._available_preset_modes.get(PresetMode.ALLERGEN)
            await self.coordinator.client.set_control_values(data=a_status_pattern)
            await asyncio.sleep(1)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("AC1214 async_set_preset_mode is called with: %s", preset_mode)

        await self._ensure_power_on()

        status_pattern = self._available_preset_modes.get(preset_mode)
        if status_pattern:
            target_mode = status_pattern.get(PhilipsApi.MODE)
            await self._ensure_mode_transition(target_mode)
            _LOGGER.debug("AC1214 sets preset mode to: %s", preset_mode)
            await self.coordinator.client.set_control_values(data=status_pattern)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the preset mode of the fan."""
        _LOGGER.debug("AC1214 async_set_percentage is called with: %s", percentage)

        await self._ensure_power_on()

        if percentage == 0:
            _LOGGER.debug("AC1214 uses 0%% to switch off")
            await self.async_turn_off()
        else:
            speed = percentage_to_ordered_list_item(self._speeds, percentage)
            status_pattern = self._available_speeds.get(speed)
            if status_pattern:
                target_mode = status_pattern.get(PhilipsApi.MODE)
                await self._ensure_mode_transition(target_mode)
                _LOGGER.debug("AC1214 sets speed percentage to: %s", percentage)
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

        await self._ensure_power_on()

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


class PhilipsAC3021(PhilipsGenericFan):
    """AC3021."""

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


class PhilipsAC303x(PhilipsAC3021):
    """AC30xx family."""

    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]


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

    AVAILABLE_SWITCHES = [PhilipsApi.CHILD_LOCK]


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
