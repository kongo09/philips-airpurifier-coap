"""Tests for entity service actions across the platforms."""

from custom_components.philips_airpurifier_coap.const import PhilipsApi
from homeassistant.core import HomeAssistant

_BASE = {
    PhilipsApi.DEVICE_ID: "ABCD1234567890",
    PhilipsApi.WIFI_VERSION: "AWS_Philips_AIR@1.0.0",
}

CX5120_STATUS = {
    **_BASE,
    PhilipsApi.NEW2_POWER: 1,
    PhilipsApi.TEMPERATURE: 20,
    PhilipsApi.NEW2_TARGET_TEMP: 21,
    PhilipsApi.NEW2_OSCILLATION: 0,
    PhilipsApi.NEW2_MODE_A: 3,
    PhilipsApi.NEW2_MODE_B: 66,
    PhilipsApi.NEW2_DISPLAY_BACKLIGHT2: 50,
}

AC2729_STATUS = {
    **_BASE,
    PhilipsApi.POWER: "1",
    PhilipsApi.FUNCTION: "PH",
    PhilipsApi.HUMIDITY: 45,
    PhilipsApi.HUMIDITY_TARGET: 50,
    PhilipsApi.MODE: "P",
    PhilipsApi.SPEED: "1",
}

AC1214_STATUS = {
    **_BASE,
    PhilipsApi.POWER: "1",
    PhilipsApi.MODE: "P",
    PhilipsApi.SPEED: "1",
}

AC3033_STATUS = {**_BASE, PhilipsApi.MODEL_ID: "AC3033/10", "ddp": "1"}


def _first(hass: HomeAssistant, domain: str) -> str:
    """Return the first entity_id of a domain."""
    return next(iter(hass.states.async_entity_ids(domain)))


async def test_climate_actions(hass: HomeAssistant, setup_model) -> None:
    """Climate service calls reach the client."""
    _, client = await setup_model("CX5120", CX5120_STATUS)
    cid = _first(hass, "climate")

    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": cid, "temperature": 22}, blocking=True
    )
    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": cid, "hvac_mode": "heat"}, blocking=True
    )
    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": cid, "hvac_mode": "off"}, blocking=True
    )
    await hass.services.async_call(
        "climate", "set_swing_mode", {"entity_id": cid, "swing_mode": "on"}, blocking=True
    )
    assert client.set_control_value.await_count >= 1


async def test_number_and_light_actions(hass: HomeAssistant, setup_model) -> None:
    """Number and light service calls reach the client."""
    _, client = await setup_model("CX5120", CX5120_STATUS)

    nid = _first(hass, "number")
    await hass.services.async_call(
        "number", "set_value", {"entity_id": nid, "value": 24}, blocking=True
    )

    lid = _first(hass, "light")
    await hass.services.async_call("light", "turn_on", {"entity_id": lid}, blocking=True)
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": lid, "brightness": 200}, blocking=True
    )
    await hass.services.async_call("light", "turn_off", {"entity_id": lid}, blocking=True)
    assert client.set_control_value.await_count >= 1


async def test_fan_oscillate(hass: HomeAssistant, setup_model) -> None:
    """Oscillation reaches the client."""
    _, client = await setup_model("CX5120", CX5120_STATUS)
    fid = _first(hass, "fan")
    await hass.services.async_call(
        "fan", "oscillate", {"entity_id": fid, "oscillating": True}, blocking=True
    )
    client.set_control_value.assert_awaited()


async def test_humidifier_actions(hass: HomeAssistant, setup_model) -> None:
    """Humidifier service calls reach the client."""
    _, client = await setup_model("AC2729", AC2729_STATUS)
    hid = _first(hass, "humidifier")

    await hass.services.async_call("humidifier", "turn_on", {"entity_id": hid}, blocking=True)
    await hass.services.async_call(
        "humidifier", "set_humidity", {"entity_id": hid, "humidity": 55}, blocking=True
    )
    await hass.services.async_call(
        "humidifier",
        "set_mode",
        {"entity_id": hid, "mode": "purification_humidification"},
        blocking=True,
    )
    # A +1 nudge from the current target snaps to a full step.
    await hass.services.async_call(
        "humidifier", "set_humidity", {"entity_id": hid, "humidity": 51}, blocking=True
    )
    await hass.services.async_call("humidifier", "turn_off", {"entity_id": hid}, blocking=True)
    assert client.set_control_value.await_count + client.set_control_values.await_count >= 1


async def test_light_auto_effect(hass: HomeAssistant, setup_model) -> None:
    """Turning a light on with the auto effect reaches the client."""
    status = {**_BASE, PhilipsApi.NEW2_POWER: 1, "D03105": 50, PhilipsApi.NEW2_MODE_B: 0}
    _, client = await setup_model("AC0950", status)
    lid = _first(hass, "light")
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": lid, "effect": "auto"}, blocking=True
    )
    client.set_control_value.assert_awaited()


async def test_ac1214_fan_special(hass: HomeAssistant, setup_model) -> None:
    """The AC1214 has bespoke preset/speed handling that reaches the client."""
    _, client = await setup_model("AC1214", AC1214_STATUS)
    fid = _first(hass, "fan")

    await hass.services.async_call(
        "fan", "set_preset_mode", {"entity_id": fid, "preset_mode": "auto"}, blocking=True
    )
    await hass.services.async_call(
        "fan", "set_percentage", {"entity_id": fid, "percentage": 50}, blocking=True
    )
    assert client.set_control_values.await_count >= 1


HU5710_STATUS = {
    **_BASE,
    PhilipsApi.NEW2_POWER: 1,
    PhilipsApi.NEW2_HUMIDITY: 45,
    "D03128": 50,  # NEW2_HUMIDITY_TARGET2 base key
    PhilipsApi.NEW2_MODE_B: 0,
}


async def test_humidifier_pure_humidification(hass: HomeAssistant, setup_model) -> None:
    """A pure humidifier (function == power) exposes the fan modes as modes."""
    _, client = await setup_model("HU5710", HU5710_STATUS)
    hid = _first(hass, "humidifier")

    modes = hass.states.get(hid).attributes["available_modes"]
    assert "auto" in modes

    await hass.services.async_call(
        "humidifier", "set_humidity", {"entity_id": hid, "humidity": 55}, blocking=True
    )
    await hass.services.async_call(
        "humidifier", "set_mode", {"entity_id": hid, "mode": "auto"}, blocking=True
    )
    assert client.set_control_value.await_count + client.set_control_values.await_count >= 1


async def test_select_action(hass: HomeAssistant, setup_model) -> None:
    """Selecting an option reaches the client."""
    _, client = await setup_model("AC3033", AC3033_STATUS)
    sid = _first(hass, "select")
    option = hass.states.get(sid).attributes["options"][0]
    await hass.services.async_call(
        "select", "select_option", {"entity_id": sid, "option": option}, blocking=True
    )
    client.set_control_value.assert_awaited()
