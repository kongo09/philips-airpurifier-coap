"""New2 generation Philips AirPurifier devices (PhilipsNew2GenericFan)."""

from __future__ import annotations

from datetime import timedelta

from ..const import (
    FanAttributes,
    PhilipsApi,
    PresetMode,
)
from .base import PhilipsGenericFanBase


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
            PhilipsApi.NEW2_GAS_PREFERRED_INDEX_MAP,
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


class PhilipsAC085020C(PhilipsAC085011C):
    """AC0850/20 with firmware AWS_Philips_AIR_Combo."""


class PhilipsAC085031C(PhilipsAC085011C):
    """AC0850/31 with firmware AWS_Philips_AIR_Combo."""


class PhilipsAC085041C(PhilipsAC085011C):
    """AC0850/41 with firmware AWS_Philips_AIR_Combo."""


class PhilipsAC085070C(PhilipsAC085011C):
    """AC0850/70 with firmware AWS_Philips_AIR_Combo."""


class PhilipsAC085081(PhilipsAC085011C):
    """AC0850/81."""


class PhilipsAC0950(PhilipsNew2GenericFan):
    """AC0950."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
            PhilipsApi.NEW2_MODE_C: 1,
        },
        PresetMode.TURBO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 18,
            PhilipsApi.NEW2_MODE_C: 18,
        },
        PresetMode.MEDIUM: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 19,
            PhilipsApi.NEW2_MODE_C: 2,
        },
        PresetMode.SLEEP: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 17,
            PhilipsApi.NEW2_MODE_C: 1,
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SLEEP: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 17,
            PhilipsApi.NEW2_MODE_C: 1,
        },
        PresetMode.MEDIUM: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 19,
            PhilipsApi.NEW2_MODE_C: 2,
        },
        PresetMode.TURBO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 18,
            PhilipsApi.NEW2_MODE_C: 18,
        },
    }
    # the prefilter data is present but doesn't change for this device, so let's take it out
    UNAVAILABLE_FILTERS = [PhilipsApi.FILTER_NANOPROTECT_PREFILTER]

    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_CHILD_LOCK, PhilipsApi.NEW2_BEEP]
    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT3]
    AVAILABLE_SELECTS = [PhilipsApi.NEW2_GAS_PREFERRED_INDEX, PhilipsApi.NEW2_TIMER2]


class PhilipsAC0951(PhilipsAC0950):
    """AC0951."""


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


# the AC22xx family shares the AC32xx API and parameters
class PhilipsAC2210(PhilipsAC32xx):
    """AC2210."""


class PhilipsAC2220(PhilipsAC2210):
    """AC2220."""


class PhilipsAC2221(PhilipsAC2210):
    """AC2221."""


class PhilipsAC3420(PhilipsNew2GenericFan):
    """AC3420."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
            PhilipsApi.NEW2_MODE_C: 3,
        },
        PresetMode.TURBO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 18,
            PhilipsApi.NEW2_MODE_C: 18,
        },
        PresetMode.MEDIUM: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 19,
            PhilipsApi.NEW2_MODE_C: 3,
        },
        PresetMode.SLEEP: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 17,
            PhilipsApi.NEW2_MODE_C: 1,
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.SPEED_1: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 1,
            PhilipsApi.NEW2_MODE_C: 1,
        },
        PresetMode.SPEED_2: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 2,
            PhilipsApi.NEW2_MODE_C: 2,
        },
        PresetMode.SPEED_3: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 3,
            PhilipsApi.NEW2_MODE_C: 3,
        },
        PresetMode.SPEED_4: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 4,
            PhilipsApi.NEW2_MODE_C: 4,
        },
        PresetMode.SPEED_5: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 5,
            PhilipsApi.NEW2_MODE_C: 18,
        },
    }

    # the prefilter data is present but doesn't change for this device, so let's take it out
    UNAVAILABLE_FILTERS = [PhilipsApi.FILTER_NANOPROTECT_PREFILTER]

    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_CHILD_LOCK, PhilipsApi.NEW2_BEEP]
    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT3]
    AVAILABLE_SELECTS = [
        PhilipsApi.NEW2_GAS_PREFERRED_INDEX,
        PhilipsApi.NEW2_TIMER2,
        PhilipsApi.NEW2_LAMP_MODE,
    ]
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.NEW2_HUMIDITY_TARGET]
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.NEW2_ERROR_CODE]


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

    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT2]
    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_CHILD_LOCK]
    UNAVAILABLE_SENSORS = [PhilipsApi.NEW2_FAN_SPEED]
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.NEW2_ERROR_CODE, PhilipsApi.NEW2_MODE_A]
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.NEW2_HUMIDITY_TARGET]


class PhilipsAC4220(PhilipsAC32xx):
    """AC4220."""

    AVAILABLE_SELECTS = [PhilipsApi.NEW2_GAS_PREFERRED_INDEX]


class PhilipsAC4221(PhilipsAC4220):
    """AC4221."""


class PhilipsAMFxxx(PhilipsNew2GenericFan):
    """AMF family."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.SLEEP: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 17,
        },
        PresetMode.TURBO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 18,
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
        PresetMode.SPEED_6: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 6,
        },
        PresetMode.SPEED_7: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 7,
        },
        PresetMode.SPEED_8: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 8,
        },
        PresetMode.SPEED_9: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 9,
        },
        PresetMode.SPEED_10: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 10,
        },
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


class PhilipsCX3120(PhilipsNew2GenericFan):
    """CX3120."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO_PLUS: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.VENTILATION: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: -127,
        },
        PresetMode.LOW: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 66,
        },
        PresetMode.MEDIUM: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 67,
        },
        PresetMode.HIGH: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 65,
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.LOW: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 66,
        },
        PresetMode.MEDIUM: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 67,
        },
        PresetMode.HIGH: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 65,
        },
    }
    KEY_OSCILLATION = {
        PhilipsApi.NEW2_OSCILLATION: PhilipsApi.OSCILLATION_MAP3,
    }

    UNAVAILABLE_SENSORS = [PhilipsApi.NEW2_FAN_SPEED, PhilipsApi.NEW2_GAS]
    AVAILABLE_SELECTS = [PhilipsApi.NEW2_TIMER2]
    AVAILABLE_NUMBERS = [PhilipsApi.NEW2_TARGET_TEMP]
    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_CHILD_LOCK]

    CREATE_FAN = True  # later set to false once everything is working
    AVAILABLE_HEATERS = [PhilipsApi.NEW2_TARGET_TEMP]


class PhilipsCX5120(PhilipsNew2GenericFan):
    """CX5120."""

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.VENTILATION: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 1,
            PhilipsApi.NEW2_MODE_B: -127,
        },
        PresetMode.LOW: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 66,
        },
        PresetMode.HIGH: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 65,
        },
    }
    AVAILABLE_SPEEDS = {
        PresetMode.LOW: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 66,
        },
        PresetMode.HIGH: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_A: 3,
            PhilipsApi.NEW2_MODE_B: 65,
        },
    }
    KEY_OSCILLATION = {
        PhilipsApi.NEW2_OSCILLATION: PhilipsApi.OSCILLATION_MAP2,
    }

    AVAILABLE_LIGHTS = [PhilipsApi.NEW2_DISPLAY_BACKLIGHT2]
    AVAILABLE_SWITCHES = [PhilipsApi.NEW2_BEEP]
    UNAVAILABLE_SENSORS = [PhilipsApi.NEW2_FAN_SPEED, PhilipsApi.NEW2_GAS]
    AVAILABLE_SELECTS = [PhilipsApi.NEW2_TIMER2]
    AVAILABLE_NUMBERS = [PhilipsApi.NEW2_TARGET_TEMP]

    CREATE_FAN = True  # later set to false once everything is working
    AVAILABLE_HEATERS = [PhilipsApi.NEW2_TARGET_TEMP]


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

    CREATE_FAN = False

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
        PresetMode.MEDIUM: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 19},
        PresetMode.HIGH: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 65},
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

    CREATE_FAN = False

    AVAILABLE_PRESET_MODES = {
        PresetMode.AUTO: {
            PhilipsApi.NEW2_POWER: 1,
            PhilipsApi.NEW2_MODE_B: 0,
        },
        PresetMode.SLEEP: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 17},
        PresetMode.MEDIUM: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 19},
        PresetMode.HIGH: {PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_MODE_B: 65},
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
    AVAILABLE_BINARY_SENSORS = [PhilipsApi.NEW2_ERROR_CODE]
    AVAILABLE_HUMIDIFIERS = [PhilipsApi.NEW2_HUMIDITY_TARGET2]
