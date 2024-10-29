"""Philips Air Purifier & Humidifier Switches."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    CONF_ENTITY_CATEGORY,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_MODEL,
    DATA_KEY_COORDINATOR,
    DIMMABLE,
    DOMAIN,
    LIGHT_TYPES,
    SWITCH_MEDIUM,
    SWITCH_OFF,
    SWITCH_ON,
    FanAttributes,
    PhilipsApi,
)
from .philips import Coordinator, PhilipsEntity, model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up the light platform."""
    _LOGGER.debug("async_setup_entry called for platform light")

    host = entry.data[CONF_HOST]
    model = entry.data[CONF_MODEL]
    name = entry.data[CONF_NAME]

    data = hass.data[DOMAIN][host]

    coordinator = data[DATA_KEY_COORDINATOR]

    model_class = model_to_class.get(model)
    if model_class:
        available_lights = []

        for cls in reversed(model_class.__mro__):
            cls_available_lights = getattr(cls, "AVAILABLE_LIGHTS", [])
            available_lights.extend(cls_available_lights)

        lights = [
            PhilipsLight(coordinator, name, model, light)
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

    def __init__(  # noqa: D107
        self, coordinator: Coordinator, name: str, model: str, light: str
    ) -> None:
        super().__init__(coordinator)
        self._model = model
        self._description = LIGHT_TYPES[light]
        self._on = self._description.get(SWITCH_ON)
        self._off = self._description.get(SWITCH_OFF)
        self._medium = self._description.get(SWITCH_MEDIUM)
        self._dimmable = self._description.get(DIMMABLE)
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        self._attr_icon = self._description.get(ATTR_ICON)
        self._attr_name = (
            f"{name} {self._description[FanAttributes.LABEL].replace('_', ' ').title()}"
        )
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)

        if self._dimmable is None:
            self._dimmable = False
            self._medium = None

        if self._dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

        try:
            device_id = self._device_status[PhilipsApi.DEVICE_ID]
            self._attr_unique_id = f"{self._model}-{device_id}-{light.lower()}"
        except KeyError as e:
            _LOGGER.error("Failed retrieving unique_id due to missing key: %s", e)
            raise PlatformNotReady from e
        except TypeError as e:
            _LOGGER.error("Failed retrieving unique_id due to type error: %s", e)
            raise PlatformNotReady from e

        self._attrs: dict[str, Any] = {}
        self.kind = light.partition("#")[0]

    @property
    def is_on(self) -> bool:
        """Return if the light is on."""
        status = int(self._device_status.get(self.kind))
        # _LOGGER.debug("is_on, kind: %s - status: %s - on: %s", self.kind, status, self._on)
        return int(status) != int(self._off)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if self._dimmable:
            brightness = int(self._device_status.get(self.kind))
            if self._medium and brightness == int(self._medium):
                return 128
            return round(255 * brightness / int(self._on))
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        if self._dimmable:
            if ATTR_BRIGHTNESS in kwargs:
                if self._medium and kwargs[ATTR_BRIGHTNESS] < 255:
                    value = self._medium
                else:
                    value = round(int(self._on) * int(kwargs[ATTR_BRIGHTNESS]) / 255)
            else:
                value = int(self._on)
        else:
            value = self._on

        _LOGGER.debug("async_turn_on, kind: %s - value: %s", self.kind, value)
        await self.coordinator.client.set_control_value(self.kind, value)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        _LOGGER.debug("async_turn_off, kind: %s - value: %s", self.kind, self._off)
        await self.coordinator.client.set_control_value(self.kind, self._off)
