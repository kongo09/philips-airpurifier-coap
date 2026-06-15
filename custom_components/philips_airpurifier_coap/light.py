"""Philips Air Purifier & Humidifier lights."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SWITCH_AUTO, FanAttributes, PhilipsApi
from .devices import PhilipsEntity, collect_class_attribute, model_to_class

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .config_entry_data import ConfigEntryData
    from .const import PhilipsConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PhilipsLightEntityDescription(LightEntityDescription):
    """Describe a Philips light entity."""

    on_value: Any = None
    off_value: Any = None
    medium_value: Any = None
    auto_value: Any = None
    dimmable: bool = False


LIGHT_TYPES: tuple[PhilipsLightEntityDescription, ...] = (
    PhilipsLightEntityDescription(
        key=PhilipsApi.DISPLAY_BACKLIGHT,
        translation_key=FanAttributes.DISPLAY_BACKLIGHT,
        entity_category=EntityCategory.CONFIG,
        on_value="1",
        off_value="0",
    ),
    PhilipsLightEntityDescription(
        key=PhilipsApi.LIGHT_BRIGHTNESS,
        translation_key=FanAttributes.LIGHT_BRIGHTNESS,
        entity_category=EntityCategory.CONFIG,
        on_value=100,
        off_value=0,
        dimmable=True,
    ),
    PhilipsLightEntityDescription(
        key=PhilipsApi.NEW_DISPLAY_BACKLIGHT,
        translation_key=FanAttributes.DISPLAY_BACKLIGHT,
        entity_category=EntityCategory.CONFIG,
        on_value=100,
        off_value=0,
    ),
    PhilipsLightEntityDescription(
        key=PhilipsApi.NEW2_DISPLAY_BACKLIGHT,
        translation_key=FanAttributes.DISPLAY_BACKLIGHT,
        entity_category=EntityCategory.CONFIG,
        on_value=100,
        off_value=0,
        dimmable=True,
    ),
    PhilipsLightEntityDescription(
        key=PhilipsApi.NEW2_DISPLAY_BACKLIGHT2,
        translation_key=FanAttributes.DISPLAY_BACKLIGHT,
        entity_category=EntityCategory.CONFIG,
        on_value=100,
        off_value=0,
        dimmable=True,
    ),
    PhilipsLightEntityDescription(
        key=PhilipsApi.NEW2_DISPLAY_BACKLIGHT3,
        translation_key=FanAttributes.DISPLAY_BACKLIGHT,
        entity_category=EntityCategory.CONFIG,
        on_value=123,
        off_value=0,
        medium_value=115,
        auto_value=101,
        dimmable=True,
    ),
    PhilipsLightEntityDescription(
        key=PhilipsApi.NEW2_DISPLAY_BACKLIGHT4,
        translation_key=FanAttributes.DISPLAY_BACKLIGHT,
        entity_category=EntityCategory.CONFIG,
        on_value=123,
        off_value=0,
        medium_value=115,
        dimmable=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhilipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light platform."""
    config_entry_data = entry.runtime_data
    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class is None:
        _LOGGER.error("Unsupported model: %s", model)
        return

    available_lights = collect_class_attribute(model_class, "AVAILABLE_LIGHTS")
    async_add_entities(
        PhilipsLight(hass, entry, config_entry_data, description)
        for description in LIGHT_TYPES
        if description.key in available_lights
    )


class PhilipsLight(PhilipsEntity, LightEntity):
    """Define a Philips AirPurifier light."""

    entity_description: PhilipsLightEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        description: PhilipsLightEntityDescription,
    ) -> None:
        """Initialize the light."""
        super().__init__(hass, config, config_entry_data)
        self.entity_description = description

        self._on = description.on_value
        self._off = description.off_value
        self._medium = description.medium_value
        self._auto = description.auto_value
        self._dimmable = description.dimmable

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
        self._attr_unique_id = f"{model}-{device_id}-{description.key.lower()}"

        # Some Philips keys are disambiguated with a "#" marker.
        self._key = description.key.partition("#")[0]

    @property
    def is_on(self) -> bool:
        """Return True if the light is on."""
        value = self._device_status.get(self._key)
        if value is None:
            return False
        return int(value) != int(self._off)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if not self._dimmable:
            return None

        if self._auto and self._attr_effect == SWITCH_AUTO:
            return None

        value = self._device_status.get(self._key)
        if value is None:
            return None
        brightness = int(value)

        # The device may switch to the auto value on its own.
        if self._auto and brightness == int(self._auto):
            self._attr_effect = SWITCH_AUTO
            return None

        if self._medium and brightness == int(self._medium):
            return 128

        if brightness == int(self._off):
            self._attr_effect = EFFECT_OFF
            return 0

        return round(255 * brightness / int(self._on))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        value: Any = self._on

        if ATTR_EFFECT in kwargs:
            self._attr_effect = kwargs[ATTR_EFFECT]
            if self._attr_effect == SWITCH_AUTO:
                value = self._auto
        elif self._dimmable:
            if ATTR_BRIGHTNESS in kwargs:
                if self._medium and kwargs[ATTR_BRIGHTNESS] < 255:
                    value = self._medium
                else:
                    value = round(int(self._on) * int(kwargs[ATTR_BRIGHTNESS]) / 255)
            else:
                value = int(self._on)

        await self._async_set_control_value(self._key, value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._attr_effect = EFFECT_OFF
        await self._async_set_control_value(self._key, self._off)
