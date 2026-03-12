"""Philips Air Purifier & Humidifier Binary Sensors."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_CATEGORY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .config_entry_data import ConfigEntryData
from .const import BINARY_SENSOR_TYPES, DOMAIN, FanAttributes
from .philips import PhilipsEntity, model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up platform for binary_sensor."""

    config_entry_data: ConfigEntryData = hass.data[DOMAIN][entry.entry_id]

    model = config_entry_data.device_information.model
    status = config_entry_data.latest_status

    model_class = model_to_class.get(model)
    available_binary_sensors = []

    if model_class:
        for cls in reversed(model_class.__mro__):
            cls_available_binary_sensors = getattr(cls, "AVAILABLE_BINARY_SENSORS", [])
            available_binary_sensors.extend(cls_available_binary_sensors)

    binary_sensors = [
        PhilipsBinarySensor(hass, entry, config_entry_data, binary_sensor)
        for binary_sensor in BINARY_SENSOR_TYPES
        if binary_sensor in status and binary_sensor in available_binary_sensors
    ]

    async_add_entities(binary_sensors, update_before_add=False)


class PhilipsBinarySensor(PhilipsEntity, BinarySensorEntity):
    """Define a Philips AirPurifier binary_sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        kind: str,
    ) -> None:
        """Initialize the binary sensor."""

        super().__init__(hass, config, config_entry_data)

        self._model = config_entry_data.device_information.model

        self._description = BINARY_SENSOR_TYPES[kind]
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)
        self._attr_translation_key = self._description.get(FanAttributes.LABEL)

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{kind.lower()}"

        self._attrs: dict[str, Any] = {}
        self.kind = kind

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        value = self._device_status[self.kind]
        convert = self._description.get(FanAttributes.VALUE)
        if convert:
            value = convert(value)
        return cast(bool, value)
