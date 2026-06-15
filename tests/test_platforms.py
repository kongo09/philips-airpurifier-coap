"""Setup and behaviour tests across the migrated entity platforms."""

from custom_components.philips_airpurifier_coap import (
    binary_sensor,
    climate,
    humidifier,
    light,
    number,
    select,
    sensor,
)
from custom_components.philips_airpurifier_coap.const import PhilipsApi
from homeassistant.core import HomeAssistant


def _status(**extra) -> dict:
    """Build a status containing the keys needed for DeviceInfo plus extras."""
    return {
        PhilipsApi.DEVICE_ID: "ABCD1234567890",
        PhilipsApi.WIFI_VERSION: "AWS_Philips_AIR@1.0.0",
        **extra,
    }


async def _setup(hass, make_runtime, module, model, status=None):
    """Run a platform setup and return the created entities."""
    entry, runtime = make_runtime(model=model, status=status)
    added: list = []
    await module.async_setup_entry(hass, entry, lambda entities, *_: added.extend(entities))
    return added, runtime


# --------------------------------------------------------------------------- #
# sensor
# --------------------------------------------------------------------------- #
async def test_sensor_setup_and_native_value(hass: HomeAssistant, make_runtime) -> None:
    """Sensors are created for keys present in the status with a stable unique_id."""
    entities, _ = await _setup(hass, make_runtime, sensor, "AC3033")
    by_key = {e.entity_description.key: e for e in entities}

    assert PhilipsApi.PM25 in by_key
    pm25 = by_key[PhilipsApi.PM25]
    assert pm25.unique_id == "AC3033-ABCD1234567890-pm25"
    assert pm25.native_value == 15


async def test_sensor_value_fn(hass: HomeAssistant, make_runtime) -> None:
    """The temperature value_fn divides the raw value by ten."""
    status = _status(**{PhilipsApi.NEW2_TEMPERATURE: 225})
    entities, _ = await _setup(hass, make_runtime, sensor, "AMF870", status)
    temp = next(e for e in entities if e.entity_description.key == PhilipsApi.NEW2_TEMPERATURE)
    assert temp.native_value == 22.5


async def test_filter_sensor(hass: HomeAssistant, make_runtime) -> None:
    """Filter sensors report a percentage and keep the label-based unique_id."""
    status = _status(
        **{
            PhilipsApi.FILTER_HEPA: 80,
            PhilipsApi.FILTER_HEPA_TOTAL: 100,
            PhilipsApi.FILTER_HEPA_TYPE: "A3",
        }
    )
    entities, _ = await _setup(hass, make_runtime, sensor, "AC3033", status)
    hepa = next(e for e in entities if isinstance(e, sensor.PhilipsFilterSensor))
    assert hepa.unique_id == "AC3033-ABCD1234567890-hepa_filter"
    assert hepa.native_value == 80


# --------------------------------------------------------------------------- #
# binary_sensor
# --------------------------------------------------------------------------- #
async def test_binary_sensor_value_fn(hass: HomeAssistant, make_runtime) -> None:
    """The water-tank binary sensor decodes bit 9 of the error code."""
    status = _status(**{PhilipsApi.NEW2_ERROR_CODE: 0})
    entities, _ = await _setup(hass, make_runtime, binary_sensor, "AC3420", status)
    water = next(
        e
        for e in entities
        if isinstance(e, binary_sensor.PhilipsBinarySensor)
        and e.entity_description.key == PhilipsApi.NEW2_ERROR_CODE
    )
    assert water.is_on is True  # no out-of-water bit set -> tank present
    assert water.unique_id == "AC3420-ABCD1234567890-d03240"


async def test_filter_alert_sensor_added(hass: HomeAssistant, make_runtime) -> None:
    """A filter-alert sensor is added when the device exposes a filter."""
    status = _status(**{PhilipsApi.FILTER_HEPA: 5, PhilipsApi.FILTER_HEPA_TOTAL: 100})
    entities, _ = await _setup(hass, make_runtime, binary_sensor, "AC3033", status)
    alert = next(e for e in entities if isinstance(e, binary_sensor.PhilipsFilterAlertSensor))
    assert alert.unique_id == "AC3033-ABCD1234567890-filter_alert"
    assert alert.is_on is True  # 5% is below the threshold


# --------------------------------------------------------------------------- #
# light
# --------------------------------------------------------------------------- #
async def test_light_is_on_handles_missing_key(hass: HomeAssistant, make_runtime) -> None:
    """light.is_on must not crash when the key is absent from the status."""
    entities, _ = await _setup(hass, make_runtime, light, "AC1214")
    assert entities  # AC1214 exposes the backlight + brightness lights
    for entity in entities:
        assert entity.is_on is False


async def test_light_unique_id_preserves_hash(hass: HomeAssistant, make_runtime) -> None:
    """The '#' marker in a key is preserved in the unique_id."""
    entities, _ = await _setup(hass, make_runtime, light, "AC0950")
    backlight = next(
        e for e in entities if e.entity_description.key == PhilipsApi.NEW2_DISPLAY_BACKLIGHT3
    )
    assert backlight.unique_id == "AC0950-ABCD1234567890-d03105#1"


async def test_light_brightness_levels(hass: HomeAssistant, make_runtime) -> None:
    """A dimmable backlight maps device values to brightness (with auto/medium)."""
    status = {**_status(), "D03105": 123}  # NEW2_DISPLAY_BACKLIGHT3 base key, full on
    entities, _ = await _setup(hass, make_runtime, light, "AC0950", status)
    backlight = next(
        e for e in entities if e.entity_description.key == PhilipsApi.NEW2_DISPLAY_BACKLIGHT3
    )

    assert backlight.is_on is True
    assert backlight.brightness == 255
    backlight._device_status["D03105"] = 115  # medium
    assert backlight.brightness == 128
    backlight._device_status["D03105"] = 0  # off
    assert backlight.brightness == 0
    backlight._device_status["D03105"] = 101  # auto
    assert backlight.brightness is None


# --------------------------------------------------------------------------- #
# number
# --------------------------------------------------------------------------- #
async def test_number_setup_and_value(hass: HomeAssistant, make_runtime) -> None:
    """The oscillation number is created with the right boundaries."""
    status = _status(**{PhilipsApi.NEW2_OSCILLATION: 90})
    entities, _ = await _setup(hass, make_runtime, number, "AMF870", status)
    osc = next(e for e in entities if e.entity_description.key == PhilipsApi.NEW2_OSCILLATION)
    assert osc.unique_id == "AMF870-ABCD1234567890-d0320f"
    assert osc.native_value == 90
    assert osc.native_max_value == 350
    assert osc.entity_description.min_value == 30


# --------------------------------------------------------------------------- #
# select
# --------------------------------------------------------------------------- #
async def test_select_current_option(hass: HomeAssistant, make_runtime) -> None:
    """A known device value maps to its option string."""
    status = _status(**{"ddp": "1"})
    entities, _ = await _setup(hass, make_runtime, select, "AC2729", status)
    pref = next(e for e in entities if e._key == "ddp")
    assert pref.current_option == "pm25"


async def test_select_current_option_none_when_unknown(hass: HomeAssistant, make_runtime) -> None:
    """An unknown device value yields None, not the string 'None'."""
    status = _status(**{"ddp": "9"})
    entities, _ = await _setup(hass, make_runtime, select, "AC2729", status)
    pref = next(e for e in entities if e._key == "ddp")
    assert pref.current_option is None


# --------------------------------------------------------------------------- #
# climate
# --------------------------------------------------------------------------- #
async def test_climate_setup_and_temperature_guard(hass: HomeAssistant, make_runtime) -> None:
    """The heater is created and set_temperature ignores a missing temperature."""
    status = _status(**{PhilipsApi.NEW2_POWER: 1, PhilipsApi.NEW2_TARGET_TEMP: 21})
    entities, runtime = await _setup(hass, make_runtime, climate, "CX3120", status)
    heater = entities[0]
    assert heater.unique_id == "CX3120-ABCD1234567890-d0310e"
    assert heater.target_temperature == 21

    # Missing temperature must be a no-op, never an exception.
    await heater.async_set_temperature()
    runtime.client.set_control_value.assert_not_called()


# --------------------------------------------------------------------------- #
# humidifier
# --------------------------------------------------------------------------- #
async def test_humidifier_setup_and_mode(hass: HomeAssistant, make_runtime) -> None:
    """A 2-in-1 humidifier reports its mode from the function key."""
    status = _status(**{PhilipsApi.POWER: "1", PhilipsApi.FUNCTION: "PH", "rh": 45, "rhset": 50})
    entities, _ = await _setup(hass, make_runtime, humidifier, "AC2729", status)
    hum = entities[0]
    assert hum.unique_id == "AC2729-ABCD1234567890-rhset"
    assert hum.mode == "purification_humidification"
    assert hum.current_humidity == 45
