"""Philips Air Purifier & Humidifier Numbers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ICON, CONF_ENTITY_CATEGORY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .config_entry_data import ConfigEntryData
from .const import DOMAIN, NUMBER_TYPES, FanAttributes
from .philips import PhilipsEntity, model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up the number platform."""

    config_entry_data: ConfigEntryData = hass.data[DOMAIN][entry.entry_id]

    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class:
        available_numbers = []

        for cls in reversed(model_class.__mro__):
            cls_available_numbers = getattr(cls, "AVAILABLE_NUMBERS", [])
            available_numbers.extend(cls_available_numbers)

        numbers = [
            PhilipsNumber(hass, entry, config_entry_data, number)
            for number in NUMBER_TYPES
            if number in available_numbers
        ]

        async_add_entities(numbers, update_before_add=False)

    else:
        _LOGGER.error("Unsupported model: %s", model)
        return


class PhilipsNumber(PhilipsEntity, NumberEntity):
    """Define a Philips AirPurifier number."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        number: str,
    ) -> None:
        """Initialize the number."""

        super().__init__(hass, config, config_entry_data)

        self._model = config_entry_data.device_information.model

        self._description = NUMBER_TYPES[number]
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        label = FanAttributes.LABEL
        label = label.partition("#")[0]
        self._attr_translation_key = self._description.get(FanAttributes.LABEL)
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)
        self._attr_icon = self._description.get(ATTR_ICON)
        self._attr_mode = "slider"  # hardwired for now
        self._attr_native_unit_of_measurement = self._description.get(FanAttributes.UNIT)

        self._attr_native_min_value = self._description.get(FanAttributes.OFF)
        self._min = self._description.get(FanAttributes.MIN)
        self._attr_native_max_value = self._description.get(FanAttributes.MAX)
        self._attr_native_step = self._description.get(FanAttributes.STEP)

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{number.lower()}"

        self._attrs: dict[str, Any] = {}
        self.kind = number

    @property
    def native_value(self) -> float | None:
        """Return the current number."""
        return self._device_status.get(self.kind)

    async def async_set_native_value(self, value: float) -> None:
        """Select a number."""

        _LOGGER.debug("async_set_native_value called with: %s", value)

        # Catch the boundaries
        if value is None or value < self._attr_native_min_value:
            value = self._attr_native_min_value
        if value % self._attr_native_step > 0:
            value = value // self._attr_native_step * self._attr_native_step
        value = max(value, self._min) if value > 0 else value
        value = min(value, self._attr_native_max_value)

        _LOGGER.debug("setting number with: %s", value)

        await self.coordinator.client.set_control_value(self.kind, int(value))
        self._device_status[self.kind] = int(value)
        self._handle_coordinator_update()
