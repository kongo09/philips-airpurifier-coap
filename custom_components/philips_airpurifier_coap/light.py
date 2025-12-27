"""Philips Air Purifier & Humidifier Switches."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_CATEGORY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .config_entry_data import ConfigEntryData
from .const import (
    DIMMABLE,
    DOMAIN,
    LIGHT_TYPES,
    SWITCH_AUTO,
    SWITCH_MEDIUM,
    SWITCH_OFF,
    SWITCH_ON,
    FanAttributes,
)
from .philips import PhilipsEntity, model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up the light platform."""

    config_entry_data: ConfigEntryData = hass.data[DOMAIN][entry.entry_id]

    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class:
        available_lights = []

        for cls in reversed(model_class.__mro__):
            cls_available_lights = getattr(cls, "AVAILABLE_LIGHTS", [])
            available_lights.extend(cls_available_lights)

        lights = [
            PhilipsLight(hass, entry, config_entry_data, light)
            for light in LIGHT_TYPES
            if light in available_lights
        ]

        async_add_entities(lights, update_before_add=False)

    else:
        _LOGGER.error("Unsupported model: %s", model)
        return


class PhilipsLight(PhilipsEntity, LightEntity):
    """Define a Philips AirPurifier light."""

    _attr_is_on: bool | None = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        light: str,
    ) -> None:
        """Initialize the light."""

        super().__init__(hass, config, config_entry_data)

        self._model = config_entry_data.device_information.model

        self._description = LIGHT_TYPES[light]
        self._on = self._description.get(SWITCH_ON)
        self._off = self._description.get(SWITCH_OFF)
        self._medium = self._description.get(SWITCH_MEDIUM)
        self._auto = self._description.get(SWITCH_AUTO)
        self._dimmable = self._description.get(DIMMABLE)
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        self._attr_translation_key = self._description.get(FanAttributes.LABEL)
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)

        if self._dimmable is None:
            self._dimmable = False
            self._medium = None
            self._auto = None

        self._attr_effect_list = None
        self._attr_effect = None

        if self._dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            if self._auto:
                self._attr_effect_list = [SWITCH_AUTO]
                self._attr_effect = EFFECT_OFF
                self._attr_supported_features |= LightEntityFeature.EFFECT
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{light.lower()}"

        self._attrs: dict[str, Any] = {}
        self.kind = light.partition("#")[0]

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        status = int(self._device_status.get(self.kind))
        return int(status) != int(self._off)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""

        if self._dimmable:
            # let's test first if the light has auto capability, and the auto effect is on
            if self._auto and self._attr_effect == SWITCH_AUTO:
                return None

            brightness = int(self._device_status.get(self.kind))

            # sometimes the device sets the brightness to the auto value but the integration doesn't yet know about this
            if self._auto and brightness == int(self._auto):
                self._attr_effect = SWITCH_AUTO
                return None

            # if the light has medium capability, and the brightness is set to medium
            if self._medium and brightness == int(self._medium):
                return 128

            # if the brightness is set to off, return 0 and set the effect to off
            if brightness == int(self._off):
                self._attr_effect = EFFECT_OFF
                return 0

            # finally, this seems to be a truly dimmable light, so return the brightness
            return round(255 * brightness / int(self._on))

        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""

        # first we test if the auto effect is set for this light
        if ATTR_EFFECT in kwargs:
            self._attr_effect = kwargs[ATTR_EFFECT]
            if self._attr_effect == SWITCH_AUTO:
                value = self._auto
            else:
                # Effect is not auto, continue to check brightness/default
                value = None
        else:
            value = None

        # if value not set by effect, check if brightness is set
        if value is None and self._dimmable:
            if ATTR_BRIGHTNESS in kwargs:
                if self._medium and kwargs[ATTR_BRIGHTNESS] < 255:
                    value = self._medium
                else:
                    value = round(int(self._on) * int(kwargs[ATTR_BRIGHTNESS]) / 255)
            else:
                value = int(self._on)

        # still no value set, so we just turn the light on
        if value is None:
            value = self._on

        await self.coordinator.client.set_control_value(self.kind, value)
        self._device_status[self.kind] = value
        self._handle_coordinator_update()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        self._attr_effect = EFFECT_OFF
        await self.coordinator.client.set_control_value(self.kind, self._off)
        self._device_status[self.kind] = self._off
        self._handle_coordinator_update()
