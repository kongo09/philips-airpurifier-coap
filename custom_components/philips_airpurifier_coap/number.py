"""Philips Air Purifier & Humidifier numbers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FanAttributes, PhilipsApi
from .devices import PhilipsEntity, collect_class_attribute, model_to_class

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .config_entry_data import ConfigEntryData
    from .const import PhilipsConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PhilipsNumberEntityDescription(NumberEntityDescription):
    """Describe a Philips number entity."""

    min_set_value: float = 0


NUMBER_TYPES: tuple[PhilipsNumberEntityDescription, ...] = (
    PhilipsNumberEntityDescription(
        key=PhilipsApi.NEW2_OSCILLATION,
        translation_key=FanAttributes.OSCILLATION,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement="°",
        native_min_value=0,
        native_max_value=350,
        native_step=5,
        min_set_value=30,
    ),
    PhilipsNumberEntityDescription(
        key=PhilipsApi.NEW2_TARGET_TEMP,
        translation_key=FanAttributes.TARGET_TEMP,
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        native_min_value=1,
        native_max_value=37,
        native_step=1,
        min_set_value=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhilipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number platform."""
    config_entry_data = entry.runtime_data
    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class is None:
        _LOGGER.error("Unsupported model: %s", model)
        return

    available_numbers = collect_class_attribute(model_class, "AVAILABLE_NUMBERS")
    async_add_entities(
        PhilipsNumber(hass, entry, config_entry_data, description)
        for description in NUMBER_TYPES
        if description.key in available_numbers
    )


class PhilipsNumber(PhilipsEntity, NumberEntity):
    """Define a Philips AirPurifier number."""

    entity_description: PhilipsNumberEntityDescription
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        description: PhilipsNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(hass, config, config_entry_data)
        self.entity_description = description

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{description.key.lower()}"

    @property
    def native_value(self) -> float | None:
        """Return the current number value."""
        return self._device_status.get(self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new number value, snapped to the configured boundaries."""
        if value is None or value < self.native_min_value:
            value = self.native_min_value
        step = self.native_step
        if step is not None and value % step > 0:
            value = value // step * step
        value = max(value, self.entity_description.min_set_value) if value > 0 else value
        value = min(value, self.native_max_value)

        await self._async_set_control_value(self.entity_description.key, int(value))
