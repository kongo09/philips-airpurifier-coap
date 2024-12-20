"""Constants for Philips AirPurifier integration."""

from __future__ import annotations

from enum import StrEnum

from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_TEMPERATURE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_ENTITY_CATEGORY,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory

from .model import (
    FilterDescription,
    HeaterDescription,
    HumidifierDescription,
    LightDescription,
    NumberDescription,
    SelectDescription,
    SensorDescription,
    SwitchDescription,
)

DOMAIN = "philips_airpurifier_coap"
MANUFACTURER = "Philips"

DATA_KEY_CLIENT = "client"
DATA_KEY_COORDINATOR = "coordinator"
DATA_KEY_FAN = "fan"

DEFAULT_NAME = "Philips AirPurifier"


class ICON(StrEnum):
    """Custom icons provided by the integration for the interface."""

    POWER_BUTTON = "pap:power_button"
    CHILD_LOCK_BUTTON = "pap:child_lock_button"
    CHILD_LOCK_BUTTON_OPEN = "pap:child_lock_button_open"
    AUTO_MODE_BUTTON = "pap:auto_mode_button"
    FAN_SPEED_BUTTON = "pap:fan_speed_button"
    HUMIDITY_BUTTON = "pap:humidity_button"
    LIGHT_DIMMING_BUTTON = "pap:light_dimming_button"
    LIGHT_FUNCTION = "pap:light_function"
    AMBIENT_LIGHT = "pap:ambient_light"
    TWO_IN_ONE_MODE_BUTTON = "pap:two_in_one_mode_button"
    SLEEP_MODE = "pap:sleep_mode"
    AUTO_MODE = "pap:auto_mode"
    SPEED_1 = "pap:speed_1"
    SPEED_2 = "pap:speed_2"
    SPEED_3 = "pap:speed_3"
    ALLERGEN_MODE = "pap:allergen_mode"
    PURIFICATION_ONLY_MODE = "pap:purification_only_mode"
    TWO_IN_ONE_MODE = "pap:two_in_one_mode"
    BACTERIA_VIRUS_MODE = "pap:bacteria_virus_mode"
    POLLUTION_MODE = "pap:pollution_mode"
    NANOPROTECT_FILTER = "pap:nanoprotect_filter"
    FILTER_REPLACEMENT = "pap:filter_replacement"
    WATER_REFILL = "pap:water_refill"
    PREFILTER_CLEANING = "pap:prefilter_cleaning"
    PREFILTER_WICK_CLEANING = "pap:prefilter_wick_cleaning"
    PM25 = "pap:pm25b"
    IAI = "pap:iai"
    CIRCULATE = "pap:circulate"
    CLEAN = "pap:clean"
    MODE = "pap:mode"
    ROTATE = "pap:rotate"
    OSCILLATE = "pap:oscillate"
    GAS = "pap:gas"
    HEATING = "pap:heating"


DATA_EXTRA_MODULE_URL = "frontend_extra_module_url"
LOADER_URL = f"/{DOMAIN}/main.js"
LOADER_PATH = f"custom_components/{DOMAIN}/main.js"
ICONS_URL = f"/{DOMAIN}/icons"
ICONLIST_URL = f"/{DOMAIN}/list"
ICONS_PATH = f"custom_components/{DOMAIN}/icons"

PAP = "pap"
ICONS = "icons"

CONF_MODEL = "model"
CONF_DEVICE_ID = "device_id"
CONF_STATUS = "status"

SWITCH_ON = "on"
TEST_ON = "on"
SWITCH_OFF = "off"
SWITCH_MEDIUM = "medium"
SWITCH_AUTO = "auto"
OPTIONS = "options"
DIMMABLE = "dimmable"


class FanModel(StrEnum):
    """Supported fan models."""

    AC0850_11 = "AC0850/11 AWS_Philips_AIR"
    AC0850_11C = "AC0850/11 AWS_Philips_AIR_Combo"
    AC0850_20 = "AC0850/20 AWS_Philips_AIR"
    AC0850_20C = "AC0850/20 AWS_Philips_AIR_Combo"
    AC0850_31 = "AC0850/31 AWS_Philips_AIR"
    AC0850_31C = "AC0850/31 AWS_Philips_AIR_Combo"
    AC0850_41 = "AC0850/41 AWS_Philips_AIR"
    AC0850_41C = "AC0850/41 AWS_Philips_AIR_Combo"
    AC0850_70 = "AC0850/70 AWS_Philips_AIR"
    AC0850_70C = "AC0850/70 AWS_Philips_AIR_Combo"
    AC0850_81 = "AC0850/81"
    AC0850_85 = "AC0850/85"
    AC0950 = "AC0950"
    AC0951 = "AC0951"
    AC1214 = "AC1214"
    AC1715 = "AC1715"
    AC2729 = "AC2729"
    AC2889 = "AC2889"
    AC2936 = "AC2936"
    AC2939 = "AC2939"
    AC2958 = "AC2958"
    AC2959 = "AC2959"
    AC3033 = "AC3033"
    AC3036 = "AC3036"
    AC3039 = "AC3039"
    AC3055 = "AC3055"
    AC3059 = "AC3059"
    AC3210 = "AC3210"
    AC3220 = "AC3220"
    AC3221 = "AC3221"
    AC3259 = "AC3259"
    AC3420 = "AC3420"
    AC3421 = "AC3421"
    AC3737 = "AC3737"
    AC3829 = "AC3829"
    AC3836 = "AC3836"
    AC3854_50 = "AC3854/50"
    AC3854_51 = "AC3854/51"
    AC3858_50 = "AC3858/50"
    AC3858_51 = "AC3858/51"
    AC3858_83 = "AC3858/83"
    AC3858_86 = "AC3858/86"
    AC4220 = "AC4220"
    AC4221 = "AC4221"
    AC4236 = "AC4236"
    AC4550 = "AC4550"
    AC4558 = "AC4558"
    AC5659 = "AC5659"
    AC5660 = "AC5660"
    AMF765 = "AMF765"
    AMF870 = "AMF870"
    CX3120 = "CX3120"
    CX3550 = "CX3550"
    CX5120 = "CX5120"
    HU1509 = "HU1509"
    HU1510 = "HU1510"
    HU5710 = "HU5710"


class PresetMode:
    """Available preset modes."""

    SPEED_1 = "speed_1"
    SPEED_GENTLE_1 = "gentle_speed_1"
    SPEED_2 = "speed_2"
    SPEED_3 = "speed_3"
    SPEED_4 = "speed_4"
    SPEED_5 = "speed_5"
    SPEED_6 = "speed_6"
    SPEED_7 = "speed_7"
    SPEED_8 = "speed_8"
    SPEED_9 = "speed_9"
    SPEED_10 = "speed_10"
    ALLERGEN = "allergen"
    AUTO = "auto"
    AUTO_GENERAL = "auto_general"
    AUTO_PLUS = "auto_plus"
    BACTERIA = "bacteria"
    GENTLE = "gentle"
    NIGHT = "night"
    SLEEP = "sleep"
    SLEEP_ALLERGY = "allergy_sleep"
    TURBO = "turbo"
    MEDIUM = "medium"
    GAS = "gas"
    POLLUTION = "pollution"
    LOW = "low"
    HIGH = "high"
    VENTILATION = "ventilation"
    NATURAL = "natural"

    ICON_MAP = {
        SPEED_1: "pap:speed_1",
        SPEED_GENTLE_1: "pap:speed_1",
        SPEED_2: "pap:speed_2",
        SPEED_3: "pap:speed_3",
        SPEED_4: "pap:fan_speed_button",
        SPEED_5: "pap:fan_speed_button",
        SPEED_6: "pap:fan_speed_button",
        SPEED_7: "pap:fan_speed_button",
        SPEED_8: "pap:fan_speed_button",
        SPEED_9: "pap:fan_speed_button",
        SPEED_10: "pap:fan_speed_button",
        ALLERGEN: "pap:allergen_mode",
        AUTO: "pap:auto_mode_button",
        AUTO_GENERAL: "pap:auto_mode_button",
        AUTO_PLUS: "pap:auto_mode_button",
        BACTERIA: "pap:bacteria_virus_mode",
        GENTLE: "pap:speed_1",
        NIGHT: "pap:sleep_mode",
        SLEEP: "pap:sleep_mode",
        SLEEP_ALLERGY: "pap:sleep_mode",
        TURBO: "pap:speed_3",
        MEDIUM: "pap:speed_2",
        GAS: "pap:gas",
        POLLUTION: "pap:pollution_mode",
        LOW: "pap:speed_1",
        HIGH: "pap:speed_3",
        VENTILATION: "pap:circulate",
        NATURAL: "pap:fan_speed_button",
    }


class FanFunction(StrEnum):
    """The function of the fan."""

    PURIFICATION = "purification"
    PURIFICATION_HUMIDIFICATION = "purification_humidification"
    FAN = "fan"
    HEATING = "heating"
    CIRCULATION = "circulation"


class FanAttributes(StrEnum):
    """The attributes of a fan."""

    ACTUAL_FAN_SPEED = "actual_fan_speed"
    AIR_QUALITY_INDEX = "air_quality_index"
    AIR_QUALITY = "air_quality"
    CHILD_LOCK = "child_lock"
    BEEP = "beep"
    DEVICE_ID = "device_id"
    DEVICE_VERSION = "device_version"
    DISPLAY_BACKLIGHT = "display_backlight"
    AUTO_DISPLAY_BACKLIGHT = "auto_display_backlight"
    ERROR_CODE = "error_code"
    ERROR = "error"
    RAW = "raw"
    TOTAL = "total"
    TIME_REMAINING = "time_remaining"
    TYPE = "type"
    FILTER_PRE = "pre_filter"
    FILTER_HEPA = "hepa_filter"
    FILTER_ACTIVE_CARBON = "active_carbon_filter"
    FILTER_WICK = "wick"
    FILTER_NANOPROTECT = "nanoprotect_filter"
    FILTER_NANOPROTECT_CLEAN = "pre_filter"
    FUNCTION = "function"
    PURIFICATION = "purification"
    HUMIDITY = "humidity"
    HUMIDIFICATION = "humidification"
    HUMIDIFIER = "humidifier"
    HUMIDIFYING = "humidifying"
    HUMIDITY_TARGET = "humidity_target"
    MAX_HUMIDITY = "max_humidity"
    MIN_HUMIDITY = "min_humidity"
    IDLE = "idle"
    INDOOR_ALLERGEN_INDEX = "indoor_allergen_index"
    LABEL = "label"
    LAMP_MODE = "lamp_mode"
    AMBIENT_LIGHT_MODE = "ambient_light_mode"
    LEVEL = "level"
    UNIT = "unit"
    VALUE = "value"
    LANGUAGE = "language"
    LIGHT_BRIGHTNESS = "light_brightness"
    MODE = "mode"
    MODEL_ID = "model_id"
    NAME = "name"
    PM25 = "pm25"
    GAS = "gas_level"
    PREFERRED_INDEX = "preferred_index"
    PRODUCT_ID = "product_id"
    RUNTIME = "runtime"
    SOFTWARE_VERSION = "software_version"
    SPEED = "speed"
    TOTAL_VOLATILE_ORGANIC_COMPOUNDS = "total_volatile_organic_compounds"
    WATER_LEVEL = "water_level"
    WIFI_VERSION = "wifi_version"
    PREFIX = "prefix"
    POSTFIX = "postfix"
    ICON_MAP = "icon_map"
    WARN_VALUE = "warn_value"
    WARN_ICON = "warn_icon"
    RSSI = "rssi"
    SWING = "swing"
    TURBO = "turbo"
    OSCILLATION = "oscillation"
    VALUE_LIST = "value_list"
    ON = "on"
    OFF = "off"
    POWER = "power"
    SWITCH = "switch"
    MIN = "min"
    MAX = "max"
    STEP = "step"
    TIMER = "timer"
    TEMPERATURE = "temperature"
    TARGET_TEMP = "target_temperature"
    MIN_TEMPERATURE = "min_temperature"
    MAX_TEMPERATURE = "max_temperature"
    STANDBY_SENSORS = "standby_sensors"
    AUTO_PLUS = "auto_plus"
    WATER_TANK = "water_tank"
    AUTO_QUICKDRY_MODE = "auto_quickdry_mode"
    QUICKDRY_MODE = "quickdry_mode"


class FanUnits(StrEnum):
    """Units used by the fan attributes."""

    LEVEL = "Level"
    INDEX = "Index"
    INDOOR_ALLERGEN_INDEX = "IAI"
    AIR_QUALITY_INDEX = "AQI"


class PhilipsApi:
    """Field names in the Philips API."""

    AIR_QUALITY_INDEX = "aqit"
    CHILD_LOCK = "cl"
    DEVICE_ID = "DeviceId"
    DEVICE_VERSION = "DeviceVersion"
    DISPLAY_BACKLIGHT = "uil"
    ERROR_CODE = "err"
    FILTER_PREFIX = "flt"
    FILTER_WICK_PREFIX = "wick"
    FILTER_STATUS = "sts"
    FILTER_TOTAL = "total"
    FILTER_TYPE = "t"
    FILTER_PRE = "fltsts0"
    FILTER_PRE_TOTAL = "flttotal0"
    FILTER_PRE_TYPE = "fltt0"
    FILTER_HEPA = "fltsts1"
    FILTER_HEPA_TOTAL = "flttotal1"
    FILTER_HEPA_TYPE = "fltt1"
    FILTER_ACTIVE_CARBON = "fltsts2"
    FILTER_ACTIVE_CARBON_TOTAL = "flttotal2"
    FILTER_ACTIVE_CARBON_TYPE = "fltt2"
    FILTER_WICK = "wicksts"
    FILTER_WICK_TOTAL = "wicktotal"
    FILTER_WICK_TYPE = "wickt"
    FILTER_NANOPROTECT_PREFILTER = "D05-13"
    FILTER_NANOPROTECT_CLEAN_TOTAL = "D05-07"
    FILTER_NANOPROTECT = "D05-14"
    FILTER_NANOPROTECT_TOTAL = "D05-08"
    FILTER_NANOPROTECT_TYPE = "D05-02"
    FUNCTION = "func"
    HUMIDITY = "rh"
    HUMIDITY_TARGET = "rhset"
    INDOOR_ALLERGEN_INDEX = "iaql"
    LANGUAGE = "language"
    LIGHT_BRIGHTNESS = "aqil"
    MODE = "mode"
    MODEL_ID = "modelid"
    NAME = "name"
    PM25 = "pm25"
    POWER = "pwr"
    # Unfortunately, the preferred index key for the index with and without gas are the same.
    # To distinguish, # is used as a separator, which is then filtered out in the select entity.
    PREFERRED_INDEX = "ddp#1"
    GAS_PREFERRED_INDEX = "ddp#2"
    PRODUCT_ID = "ProductId"
    RUNTIME = "Runtime"
    SOFTWARE_VERSION = "swversion"
    SPEED = "om"
    TEMPERATURE = "temp"
    TOTAL_VOLATILE_ORGANIC_COMPOUNDS = "tvoc"
    TYPE = "type"
    WATER_LEVEL = "wl"
    WIFI_VERSION = "WifiVersion"
    RSSI = "rssi"

    POWER_MAP = {
        SWITCH_ON: "1",
        SWITCH_OFF: "0",
    }

    OSCILLATION_MAP = {
        SWITCH_ON: 17920,
        SWITCH_OFF: 0,
    }
    OSCILLATION_MAP2 = {
        SWITCH_ON: 17242,
        SWITCH_OFF: 0,
    }
    OSCILLATION_MAP3 = {
        SWITCH_ON: 45,
        SWITCH_OFF: 0,
    }

    # the AC1715 seems to follow a new scheme, this should later be refactored
    NEW_NAME = "D01-03"
    NEW_MODEL_ID = "D01-05"
    NEW_LANGUAGE = "D01-07"
    NEW_SOFTWARE_VERSION = "D01-21"
    NEW_POWER = "D03-02"
    NEW_DISPLAY_BACKLIGHT = "D03-05"
    NEW_MODE = "D03-12"
    NEW_INDOOR_ALLERGEN_INDEX = "D03-32"
    NEW_PM25 = "D03-33"
    NEW_PREFERRED_INDEX = "D03-42"

    # there is a third generation of devices with yet another scheme
    NEW2_NAME = "D01S03"
    NEW2_MODEL_ID = "D01S05"
    NEW2_POWER = "D03102"
    NEW2_DISPLAY_BACKLIGHT = "D0312D"
    NEW2_DISPLAY_BACKLIGHT2 = "D03105"
    NEW2_DISPLAY_BACKLIGHT3 = "D03105#1"  # dimmable in 3 steps with auto
    NEW2_DISPLAY_BACKLIGHT4 = "D03105#2"  # dimmable in 3 steps
    NEW2_LAMP_MODE = "D03135#1"
    NEW2_LAMP_MODE2 = "D03135#2"
    NEW2_AMBIENT_LIGHT_MODE = "D03137"
    NEW2_TEMPERATURE = "D03224"
    NEW2_SOFTWARE_VERSION = "D01S12"
    NEW2_CHILD_LOCK = "D03103"
    NEW2_BEEP = "D03130"
    NEW2_INDOOR_ALLERGEN_INDEX = "D03120"
    NEW2_PM25 = "D03221"
    NEW2_GAS = "D03122"
    NEW2_HUMIDITY = "D03125"
    NEW2_ERROR_CODE = "D03240"
    NEW2_HUMIDITY_TARGET = "D03128#1"
    NEW2_HUMIDITY_TARGET2 = "D03128#2"
    NEW2_HUMIDIFYING = "D0312B"
    NEW2_FILTER_NANOPROTECT_PREFILTER = "D0520D"
    NEW2_FILTER_NANOPROTECT = "D0540E"
    NEW2_FILTER_NANOPROTECT_PREFILTER_TOTAL = "D05207"
    NEW2_FILTER_NANOPROTECT_TOTAL = "D05408"
    NEW2_FAN_SPEED = "D0310D"
    NEW2_SWING = "D0320F"
    NEW2_CIRCULATION = "D0310A#1"
    NEW2_HEATING = "D0310A#2"
    NEW2_OSCILLATION = "D0320F"
    NEW2_MODE_A = "D0310A"
    NEW2_MODE_B = "D0310C"
    NEW2_MODE_C = "D0310D"
    NEW2_TIMER = "D03110#1"
    NEW2_TIMER2 = "D03110#2"
    NEW2_AUTO_QUICKDRY_MODE = "D03138"
    NEW2_QUICKDRY_MODE = "D03139"
    NEW2_REMAINING_TIME = "D03211"
    NEW2_TARGET_TEMP = "D0310E"
    NEW2_STANDBY_SENSORS = "D03134"
    NEW2_AUTO_PLUS_AI = "D03180"
    NEW2_PREFERRED_INDEX = "D0312A#1"
    NEW2_GAS_PREFERRED_INDEX = "D0312A#2"

    LAMP_MODE_MAP = {
        0: FanAttributes.OFF,
        1: FanAttributes.AIR_QUALITY,
        2: FanAttributes.AMBIENT_LIGHT_MODE,
    }
    LAMP_MODE_MAP2 = {
        0: FanAttributes.OFF,
        1: FanAttributes.HUMIDITY,
        2: FanAttributes.AMBIENT_LIGHT_MODE,
    }
    AMBIENT_LIGHT_MODE_MAP = {
        1: "warm",
        2: "dawn",
        3: "calm",
        4: "breath",
    }
    PREFERRED_INDEX_MAP = {
        "0": FanAttributes.INDOOR_ALLERGEN_INDEX,
        "1": FanAttributes.PM25,
    }
    NEW2_PREFERRED_INDEX_MAP = {
        0: FanAttributes.INDOOR_ALLERGEN_INDEX,
        1: FanAttributes.PM25,
    }
    GAS_PREFERRED_INDEX_MAP = {
        "0": FanAttributes.INDOOR_ALLERGEN_INDEX,
        "1": FanAttributes.PM25,
        "2": FanAttributes.GAS,
    }
    NEW2_GAS_PREFERRED_INDEX_MAP = {
        0: FanAttributes.INDOOR_ALLERGEN_INDEX,
        1: FanAttributes.PM25,
        2: FanAttributes.GAS,
    }
    NEW_PREFERRED_INDEX_MAP = {
        "IAI": FanAttributes.INDOOR_ALLERGEN_INDEX,
        "PM2.5": FanAttributes.PM25,
    }
    FUNCTION_MAP = {
        "P": FanFunction.PURIFICATION,
        "PH": FanFunction.PURIFICATION_HUMIDIFICATION,
    }
    CIRCULATION_MAP = {
        1: FanFunction.FAN,
        2: FanFunction.CIRCULATION,
    }
    HEATING_MAP = {
        1: FanFunction.FAN,
        2: FanFunction.CIRCULATION,
        3: FanFunction.HEATING,
    }
    TIMER_MAP = {
        0: "Off",
        1: "30min",
        2: "1h",
        3: "2h",
        4: "3h",
        5: "4h",
        6: "5h",
        7: "6h",
        8: "7h",
        9: "8h",
        10: "9h",
        11: "10h",
        12: "11h",
        13: "12h",
    }
    TIMER2_MAP = {
        0: "Off",
        2: "1h",
        3: "2h",
        4: "3h",
        5: "4h",
        6: "5h",
        7: "6h",
        8: "7h",
        9: "8h",
        10: "9h",
        11: "10h",
        12: "11h",
        13: "12h",
    }
    # HUMIDITY_TARGET_MAP = {
    #     40: "40%",
    #     50: "50%",
    #     60: "60%",
    #     70: "max",
    # }


SENSOR_TYPES: dict[str, SensorDescription] = {
    # device sensors
    # NOTE: removed AQI as this turns out not to be a sensor, but a setting of the mobile app
    # PhilipsApi.AIR_QUALITY_INDEX: {
    #     ATTR_DEVICE_CLASS: SensorDeviceClass.AQI,
    #     FanAttributes.ICON_MAP: {0: "mdi:blur"},
    #     FanAttributes.LABEL: FanAttributes.AIR_QUALITY_INDEX,
    #     ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    # },
    PhilipsApi.INDOOR_ALLERGEN_INDEX: {
        FanAttributes.LABEL: FanAttributes.INDOOR_ALLERGEN_INDEX,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    PhilipsApi.NEW_INDOOR_ALLERGEN_INDEX: {
        FanAttributes.LABEL: FanAttributes.INDOOR_ALLERGEN_INDEX,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    PhilipsApi.NEW2_INDOOR_ALLERGEN_INDEX: {
        FanAttributes.LABEL: FanAttributes.INDOOR_ALLERGEN_INDEX,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    PhilipsApi.PM25: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.PM25,
        FanAttributes.LABEL: FanAttributes.PM25,
        FanAttributes.UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    PhilipsApi.NEW_PM25: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.PM25,
        FanAttributes.LABEL: FanAttributes.PM25,
        FanAttributes.UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    PhilipsApi.NEW2_PM25: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.PM25,
        FanAttributes.LABEL: FanAttributes.PM25,
        FanAttributes.UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    PhilipsApi.NEW2_GAS: {
        FanAttributes.LABEL: FanAttributes.GAS,
        FanAttributes.UNIT: "L",
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    PhilipsApi.TOTAL_VOLATILE_ORGANIC_COMPOUNDS: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        FanAttributes.LABEL: FanAttributes.TOTAL_VOLATILE_ORGANIC_COMPOUNDS,
        FanAttributes.UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    },
    PhilipsApi.HUMIDITY: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        FanAttributes.LABEL: FanAttributes.HUMIDITY,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        FanAttributes.UNIT: PERCENTAGE,
    },
    PhilipsApi.NEW2_HUMIDITY: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        FanAttributes.LABEL: FanAttributes.HUMIDITY,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        FanAttributes.UNIT: PERCENTAGE,
    },
    PhilipsApi.NEW2_REMAINING_TIME: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.DURATION,
        FanAttributes.LABEL: FanAttributes.TIME_REMAINING,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        FanAttributes.UNIT: UnitOfTime.MINUTES,
    },
    PhilipsApi.TEMPERATURE: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        FanAttributes.ICON_MAP: {
            0: "mdi:thermometer-low",
            17: "mdi:thermometer",
            23: "mdi:thermometer-high",
        },
        FanAttributes.LABEL: ATTR_TEMPERATURE,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        FanAttributes.UNIT: UnitOfTemperature.CELSIUS,
    },
    PhilipsApi.NEW2_TEMPERATURE: {
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        FanAttributes.ICON_MAP: {
            0: "mdi:thermometer-low",
            17: "mdi:thermometer",
            23: "mdi:thermometer-high",
        },
        FanAttributes.LABEL: ATTR_TEMPERATURE,
        FanAttributes.VALUE: lambda value, _: value / 10,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        FanAttributes.UNIT: UnitOfTemperature.CELSIUS,
    },
    # PhilipsApi.NEW2_FAN_SPEED: {
    #     FanAttributes.ICON_MAP: {
    #         0: ICON.FAN_SPEED_BUTTON,
    #         1: ICON.SPEED_1,
    #         6: ICON.SPEED_2,
    #         18: ICON.SPEED_3,
    #     },
    #     FanAttributes.VALUE: lambda value, _: value
    #     if int(value) < 18
    #     else FanAttributes.TURBO,
    #     FanAttributes.LABEL: FanAttributes.ACTUAL_FAN_SPEED,
    #     ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
    # },
    # diagnostic information
    PhilipsApi.WATER_LEVEL: {
        FanAttributes.ICON_MAP: {0: ICON.WATER_REFILL, 10: "mdi:water"},
        FanAttributes.LABEL: FanAttributes.WATER_LEVEL,
        FanAttributes.VALUE: lambda value, status: 0
        if status.get("err") in [32768, 49408]
        else value,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        FanAttributes.UNIT: PERCENTAGE,
        CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
    },
    PhilipsApi.RSSI: {
        FanAttributes.ICON_MAP: {
            -150: "mdi:wifi-strength-off-outline",
            -90: "mdi:wifi-strength-outline",
            -80: "mdi:wifi-strength-1",
            -70: "mdi:wifi-strength-2",
            -67: "mdi:wifi-strength-3",
            -30: "mdi:wifi-strength-4",
        },
        FanAttributes.LABEL: FanAttributes.RSSI,
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_DEVICE_CLASS: SensorDeviceClass.SIGNAL_STRENGTH,
        FanAttributes.UNIT: SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
    },
    # PhilipsApi.RUNTIME: {
    #     FanAttributes.ICON_MAP: {0: "mdi:timer"},
    #     FanAttributes.LABEL: FanAttributes.RUNTIME,
    #     ATTR_STATE_CLASS: SensorStateClass.TOTAL,
    #     ATTR_DEVICE_CLASS: SensorDeviceClass.DURATION,
    #     FanAttributes.UNIT: UnitOfTime.MILLISECONDS,
    #     CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
    # },
}


EXTRA_SENSOR_TYPES: dict[str, SensorDescription] = {}

BINARY_SENSOR_TYPES: dict[str, SensorDescription] = {
    # binary device sensors
    PhilipsApi.ERROR_CODE: {
        # test for out of water error, which is in bit 9 of the error number
        FanAttributes.LABEL: FanAttributes.WATER_TANK,
        ATTR_DEVICE_CLASS: SensorDeviceClass.MOISTURE,
        FanAttributes.VALUE: lambda value: not value & (1 << 8),
        CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
    },
    PhilipsApi.NEW2_ERROR_CODE: {
        # test for out of water error, which is in bit 9 of the error number
        FanAttributes.LABEL: FanAttributes.WATER_TANK,
        ATTR_DEVICE_CLASS: SensorDeviceClass.MOISTURE,
        FanAttributes.VALUE: lambda value: not value & (1 << 8),
        CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
    },
    PhilipsApi.FUNCTION: {
        # test if the water container is available and thus humidification switched on
        FanAttributes.LABEL: FanAttributes.HUMIDIFICATION,
        FanAttributes.VALUE: lambda value: value == "PH",
    },
    PhilipsApi.NEW2_MODE_A: {
        # test if the water container is available and thus humidification switched on
        FanAttributes.LABEL: FanAttributes.HUMIDIFICATION,
        FanAttributes.VALUE: lambda value: value == 4,
    },
}

FILTER_TYPES: dict[str, FilterDescription] = {
    PhilipsApi.FILTER_PRE: {
        FanAttributes.ICON_MAP: {0: ICON.FILTER_REPLACEMENT, 72: "mdi:dots-grid"},
        FanAttributes.LABEL: FanAttributes.FILTER_PRE,
        FanAttributes.TOTAL: PhilipsApi.FILTER_PRE_TOTAL,
        FanAttributes.TYPE: PhilipsApi.FILTER_PRE_TYPE,
    },
    PhilipsApi.FILTER_HEPA: {
        FanAttributes.ICON_MAP: {0: ICON.FILTER_REPLACEMENT, 72: "mdi:dots-grid"},
        FanAttributes.LABEL: FanAttributes.FILTER_HEPA,
        FanAttributes.TOTAL: PhilipsApi.FILTER_HEPA_TOTAL,
        FanAttributes.TYPE: PhilipsApi.FILTER_HEPA_TYPE,
    },
    PhilipsApi.FILTER_ACTIVE_CARBON: {
        FanAttributes.ICON_MAP: {0: ICON.FILTER_REPLACEMENT, 72: "mdi:dots-grid"},
        FanAttributes.LABEL: FanAttributes.FILTER_ACTIVE_CARBON,
        FanAttributes.TOTAL: PhilipsApi.FILTER_ACTIVE_CARBON_TOTAL,
        FanAttributes.TYPE: PhilipsApi.FILTER_ACTIVE_CARBON_TYPE,
    },
    PhilipsApi.FILTER_WICK: {
        FanAttributes.ICON_MAP: {0: ICON.PREFILTER_WICK_CLEANING, 72: "mdi:dots-grid"},
        FanAttributes.LABEL: FanAttributes.FILTER_WICK,
        FanAttributes.TOTAL: PhilipsApi.FILTER_WICK_TOTAL,
        FanAttributes.TYPE: PhilipsApi.FILTER_WICK_TYPE,
    },
    PhilipsApi.FILTER_NANOPROTECT: {
        FanAttributes.ICON_MAP: {
            0: ICON.FILTER_REPLACEMENT,
            10: ICON.NANOPROTECT_FILTER,
        },
        FanAttributes.LABEL: FanAttributes.FILTER_NANOPROTECT,
        FanAttributes.TOTAL: PhilipsApi.FILTER_NANOPROTECT_TOTAL,
        FanAttributes.TYPE: PhilipsApi.FILTER_NANOPROTECT_TYPE,
    },
    PhilipsApi.FILTER_NANOPROTECT_PREFILTER: {
        FanAttributes.ICON_MAP: {
            0: ICON.PREFILTER_CLEANING,
            10: ICON.NANOPROTECT_FILTER,
        },
        FanAttributes.LABEL: FanAttributes.FILTER_NANOPROTECT_CLEAN,
        FanAttributes.TOTAL: PhilipsApi.FILTER_NANOPROTECT_CLEAN_TOTAL,
        FanAttributes.TYPE: "",
    },
    PhilipsApi.NEW2_FILTER_NANOPROTECT: {
        FanAttributes.ICON_MAP: {
            0: ICON.FILTER_REPLACEMENT,
            10: ICON.NANOPROTECT_FILTER,
        },
        FanAttributes.LABEL: FanAttributes.FILTER_NANOPROTECT,
        FanAttributes.TOTAL: PhilipsApi.NEW2_FILTER_NANOPROTECT_TOTAL,
        FanAttributes.TYPE: "",
    },
    PhilipsApi.NEW2_FILTER_NANOPROTECT_PREFILTER: {
        FanAttributes.ICON_MAP: {
            0: ICON.PREFILTER_CLEANING,
            10: ICON.NANOPROTECT_FILTER,
        },
        FanAttributes.LABEL: FanAttributes.FILTER_NANOPROTECT_CLEAN,
        FanAttributes.TOTAL: PhilipsApi.NEW2_FILTER_NANOPROTECT_PREFILTER_TOTAL,
        FanAttributes.TYPE: "",
    },
}

SWITCH_TYPES: dict[str, SwitchDescription] = {
    PhilipsApi.CHILD_LOCK: {
        FanAttributes.LABEL: FanAttributes.CHILD_LOCK,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: True,
        SWITCH_OFF: False,
    },
    PhilipsApi.NEW2_CHILD_LOCK: {
        FanAttributes.LABEL: FanAttributes.CHILD_LOCK,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: 1,
        SWITCH_OFF: 0,
    },
    PhilipsApi.NEW2_BEEP: {
        FanAttributes.LABEL: FanAttributes.BEEP,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: 100,
        SWITCH_OFF: 0,
    },
    PhilipsApi.NEW2_STANDBY_SENSORS: {
        FanAttributes.LABEL: FanAttributes.STANDBY_SENSORS,
        SWITCH_ON: 1,
        SWITCH_OFF: 0,
    },
    PhilipsApi.NEW2_AUTO_PLUS_AI: {
        FanAttributes.LABEL: FanAttributes.AUTO_PLUS,
        SWITCH_ON: 1,
        SWITCH_OFF: 0,
    },
    PhilipsApi.NEW2_AUTO_QUICKDRY_MODE: {
        FanAttributes.LABEL: FanAttributes.AUTO_QUICKDRY_MODE,
        SWITCH_ON: 1,
        SWITCH_OFF: 0,
    },
    PhilipsApi.NEW2_QUICKDRY_MODE: {
        FanAttributes.LABEL: FanAttributes.QUICKDRY_MODE,
        SWITCH_ON: 1,
        SWITCH_OFF: 0,
    },
}

LIGHT_TYPES: dict[str, LightDescription] = {
    PhilipsApi.DISPLAY_BACKLIGHT: {
        FanAttributes.LABEL: FanAttributes.DISPLAY_BACKLIGHT,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: "1",
        SWITCH_OFF: "0",
    },
    PhilipsApi.LIGHT_BRIGHTNESS: {
        FanAttributes.LABEL: FanAttributes.LIGHT_BRIGHTNESS,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: 100,
        SWITCH_OFF: 0,
        DIMMABLE: True,
    },
    PhilipsApi.NEW_DISPLAY_BACKLIGHT: {
        FanAttributes.LABEL: FanAttributes.DISPLAY_BACKLIGHT,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: 100,
        SWITCH_OFF: 0,
    },
    PhilipsApi.NEW2_DISPLAY_BACKLIGHT: {
        FanAttributes.LABEL: FanAttributes.DISPLAY_BACKLIGHT,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: 100,
        SWITCH_OFF: 0,
        DIMMABLE: True,
    },
    PhilipsApi.NEW2_DISPLAY_BACKLIGHT2: {
        FanAttributes.LABEL: FanAttributes.DISPLAY_BACKLIGHT,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: 100,
        SWITCH_OFF: 0,
        DIMMABLE: True,
    },
    PhilipsApi.NEW2_DISPLAY_BACKLIGHT3: {
        FanAttributes.LABEL: FanAttributes.DISPLAY_BACKLIGHT,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: 123,
        SWITCH_OFF: 0,
        SWITCH_MEDIUM: 115,
        SWITCH_AUTO: 101,
        DIMMABLE: True,
    },
    PhilipsApi.NEW2_DISPLAY_BACKLIGHT4: {
        FanAttributes.LABEL: FanAttributes.DISPLAY_BACKLIGHT,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        SWITCH_ON: 123,
        SWITCH_OFF: 0,
        SWITCH_MEDIUM: 115,
        DIMMABLE: True,
    },
}

SELECT_TYPES: dict[str, SelectDescription] = {
    PhilipsApi.FUNCTION: {
        FanAttributes.LABEL: FanAttributes.FUNCTION,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.FUNCTION_MAP,
    },
    # PhilipsApi.HUMIDITY_TARGET: {
    #     FanAttributes.LABEL: FanAttributes.HUMIDITY_TARGET,
    #     CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
    #     OPTIONS: PhilipsApi.HUMIDITY_TARGET_MAP,
    # },
    # PhilipsApi.NEW2_HUMIDITY_TARGET: {
    #     FanAttributes.LABEL: FanAttributes.HUMIDITY_TARGET,
    #     CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
    #     OPTIONS: PhilipsApi.HUMIDITY_TARGET_MAP,
    # },
    PhilipsApi.NEW2_LAMP_MODE: {
        FanAttributes.LABEL: FanAttributes.LAMP_MODE,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.LAMP_MODE_MAP,
    },
    PhilipsApi.NEW2_LAMP_MODE2: {
        FanAttributes.LABEL: FanAttributes.LAMP_MODE,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.LAMP_MODE_MAP2,
    },
    PhilipsApi.NEW2_AMBIENT_LIGHT_MODE: {
        FanAttributes.LABEL: FanAttributes.AMBIENT_LIGHT_MODE,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.AMBIENT_LIGHT_MODE_MAP,
    },
    PhilipsApi.PREFERRED_INDEX: {
        FanAttributes.LABEL: FanAttributes.PREFERRED_INDEX,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.PREFERRED_INDEX_MAP,
    },
    PhilipsApi.NEW_PREFERRED_INDEX: {
        FanAttributes.LABEL: FanAttributes.PREFERRED_INDEX,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.NEW_PREFERRED_INDEX_MAP,
    },
    PhilipsApi.NEW2_PREFERRED_INDEX: {
        FanAttributes.LABEL: FanAttributes.PREFERRED_INDEX,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.NEW2_PREFERRED_INDEX_MAP,
    },
    PhilipsApi.GAS_PREFERRED_INDEX: {
        FanAttributes.LABEL: FanAttributes.PREFERRED_INDEX,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.GAS_PREFERRED_INDEX_MAP,
    },
    PhilipsApi.NEW2_GAS_PREFERRED_INDEX: {
        FanAttributes.LABEL: FanAttributes.PREFERRED_INDEX,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.NEW2_GAS_PREFERRED_INDEX_MAP,
    },
    PhilipsApi.NEW2_CIRCULATION: {
        FanAttributes.LABEL: FanAttributes.FUNCTION,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.CIRCULATION_MAP,
    },
    PhilipsApi.NEW2_HEATING: {
        FanAttributes.LABEL: FanAttributes.FUNCTION,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.HEATING_MAP,
    },
    PhilipsApi.NEW2_TIMER: {
        FanAttributes.LABEL: FanAttributes.TIMER,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.TIMER_MAP,
    },
    PhilipsApi.NEW2_TIMER2: {
        FanAttributes.LABEL: FanAttributes.TIMER,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        OPTIONS: PhilipsApi.TIMER2_MAP,
    },
}

NUMBER_TYPES: dict[str, NumberDescription] = {
    PhilipsApi.NEW2_OSCILLATION: {
        FanAttributes.LABEL: FanAttributes.OSCILLATION,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        FanAttributes.UNIT: "°",
        FanAttributes.OFF: 0,
        FanAttributes.MIN: 30,
        FanAttributes.MAX: 350,
        FanAttributes.STEP: 5,
    },
    PhilipsApi.NEW2_TARGET_TEMP: {
        FanAttributes.LABEL: FanAttributes.TARGET_TEMP,
        CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
        ATTR_DEVICE_CLASS: NumberDeviceClass.TEMPERATURE,
        FanAttributes.UNIT: "°C",
        FanAttributes.OFF: 1,
        FanAttributes.MIN: 1,
        FanAttributes.MAX: 37,
        FanAttributes.STEP: 1,
    },
    # PhilipsApi.NEW2_HUMIDITY_TARGET2: {
    #     FanAttributes.LABEL: FanAttributes.HUMIDITY_TARGET,
    #     CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
    #     FanAttributes.UNIT: PERCENTAGE,
    #     FanAttributes.OFF: 30,
    #     FanAttributes.MIN: 30,
    #     FanAttributes.MAX: 70,
    #     FanAttributes.STEP: 5,
    # },
}

HUMIDIFIER_TYPES: dict[str, HumidifierDescription] = {
    PhilipsApi.HUMIDITY_TARGET: {
        FanAttributes.LABEL: FanAttributes.HUMIDIFIER,
        FanAttributes.HUMIDITY: PhilipsApi.HUMIDITY,
        FanAttributes.POWER: PhilipsApi.POWER,
        FanAttributes.ON: PhilipsApi.POWER_MAP[SWITCH_ON],
        FanAttributes.OFF: PhilipsApi.POWER_MAP[SWITCH_OFF],
        FanAttributes.FUNCTION: PhilipsApi.FUNCTION,
        FanAttributes.HUMIDIFYING: "PH",
        FanAttributes.IDLE: "P",
        FanAttributes.SWITCH: True,
        FanAttributes.MAX_HUMIDITY: 70,
        FanAttributes.MIN_HUMIDITY: 40,
        FanAttributes.STEP: 10,
    },
    PhilipsApi.NEW2_HUMIDITY_TARGET: {
        FanAttributes.LABEL: FanAttributes.HUMIDIFIER,
        FanAttributes.HUMIDITY: PhilipsApi.NEW2_HUMIDITY,
        FanAttributes.POWER: PhilipsApi.NEW2_POWER,
        FanAttributes.ON: 1,
        FanAttributes.OFF: 0,
        FanAttributes.FUNCTION: PhilipsApi.NEW2_MODE_C,
        FanAttributes.HUMIDIFYING: 1,
        FanAttributes.IDLE: 5,
        FanAttributes.SWITCH: False,
        FanAttributes.MAX_HUMIDITY: 70,
        FanAttributes.MIN_HUMIDITY: 40,
        FanAttributes.STEP: 10,
    },
    PhilipsApi.NEW2_HUMIDITY_TARGET2: {
        FanAttributes.LABEL: FanAttributes.HUMIDIFIER,
        FanAttributes.HUMIDITY: PhilipsApi.NEW2_HUMIDITY,
        FanAttributes.POWER: PhilipsApi.NEW2_POWER,
        FanAttributes.ON: 1,
        FanAttributes.OFF: 0,
        FanAttributes.FUNCTION: PhilipsApi.NEW2_POWER,
        FanAttributes.HUMIDIFYING: 1,
        FanAttributes.IDLE: 0,
        FanAttributes.SWITCH: False,
        FanAttributes.MAX_HUMIDITY: 70,
        FanAttributes.MIN_HUMIDITY: 30,
        FanAttributes.STEP: 5,
    },
}

HEATER_TYPES: dict[str, HeaterDescription] = {
    PhilipsApi.NEW2_TARGET_TEMP: {
        FanAttributes.TEMPERATURE: PhilipsApi.TEMPERATURE,
        FanAttributes.POWER: PhilipsApi.NEW2_POWER,
        FanAttributes.ON: 1,
        FanAttributes.OFF: 0,
        FanAttributes.MIN_TEMPERATURE: 1,
        FanAttributes.MAX_TEMPERATURE: 37,
        FanAttributes.STEP: 1,
    },
}
