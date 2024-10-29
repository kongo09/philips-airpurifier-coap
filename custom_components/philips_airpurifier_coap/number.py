"""Philips Air Purifier & Humidifier Numbers."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.number import NumberEntity
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
    DOMAIN,
    NUMBER_TYPES,
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
    """Set up the number platform."""
    _LOGGER.debug("async_setup_entry called for platform number")

    host = entry.data[CONF_HOST]
    model = entry.data[CONF_MODEL]
    name = entry.data[CONF_NAME]

    data = hass.data[DOMAIN][host]

    coordinator = data[DATA_KEY_COORDINATOR]

    model_class = model_to_class.get(model)
    if model_class:
        available_numbers = []

        for cls in reversed(model_class.__mro__):
            cls_available_numbers = getattr(cls, "AVAILABLE_NUMBERS", [])
            available_numbers.extend(cls_available_numbers)

        numbers = [
            PhilipsNumber(coordinator, name, model, number)
            for number in NUMBER_TYPES
            if number in available_numbers
        ]

        async_add_entities(numbers, update_before_add=False)

    else:
        _LOGGER.error("Unsupported model: %s", model)
        return


class PhilipsNumber(PhilipsEntity, NumberEntity):
    """Define a Philips AirPurifier number."""

    def __init__(  # noqa: D107
        self, coordinator: Coordinator, name: str, model: str, number: str
    ) -> None:
        super().__init__(coordinator)
        self._model = model
        self._description = NUMBER_TYPES[number]
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        label = FanAttributes.LABEL
        label = label.partition("#")[0]
        self._attr_name = f"{name} {self._description[label].replace('_', ' ').title()}"
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)
        self._attr_icon = self._description.get(ATTR_ICON)
        self._attr_mode = "slider"  # hardwired for now
        self._attr_native_unit_of_measurement = self._description.get(
            FanAttributes.UNIT
        )

        self._attr_native_min_value = self._description.get(FanAttributes.OFF)
        self._min = self._description.get(FanAttributes.MIN)
        self._attr_native_max_value = self._description.get(FanAttributes.MAX)
        self._attr_native_step = self._description.get(FanAttributes.STEP)

        try:
            device_id = self._device_status[PhilipsApi.DEVICE_ID]
            self._attr_unique_id = f"{self._model}-{device_id}-{number.lower()}"
        except KeyError as e:
            _LOGGER.error("Failed retrieving unique_id due to missing key: %s", e)
            raise PlatformNotReady from e
        except TypeError as e:
            _LOGGER.error("Failed retrieving unique_id due to type error: %s", e)
            raise PlatformNotReady from e

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
