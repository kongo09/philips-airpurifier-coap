"""Philips Air Purifier & Humidifier Binary Sensors."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, cast

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity

from .const import (
    BINARY_SENSOR_TYPES,
    CONF_MODEL,
    DATA_KEY_COORDINATOR,
    DOMAIN,
    FanAttributes,
    PhilipsApi,
)
from .philips import Coordinator, PhilipsEntity, model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(  # noqa: D103
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    _LOGGER.debug("async_setup_entry called for platform binary_sensor")

    host = entry.data[CONF_HOST]
    model = entry.data[CONF_MODEL]
    name = entry.data[CONF_NAME]

    data = hass.data[DOMAIN][host]

    coordinator = data[DATA_KEY_COORDINATOR]
    status = coordinator.status

    model_class = model_to_class.get(model)
    available_binary_sensors = []

    if model_class:
        for cls in reversed(model_class.__mro__):
            cls_available_binary_sensors = getattr(cls, "AVAILABLE_BINARY_SENSORS", [])
            available_binary_sensors.extend(cls_available_binary_sensors)

    binary_sensors = [
        PhilipsBinarySensor(coordinator, name, model, binary_sensor)
        for binary_sensor in BINARY_SENSOR_TYPES
        if binary_sensor in status and binary_sensor in available_binary_sensors
    ]

    async_add_entities(binary_sensors, update_before_add=False)


class PhilipsBinarySensor(PhilipsEntity, BinarySensorEntity):
    """Define a Philips AirPurifier binary_sensor."""

    def __init__(  # noqa: D107
        self, coordinator: Coordinator, name: str, model: str, kind: str
    ) -> None:
        super().__init__(coordinator)
        self._model = model
        self._description = BINARY_SENSOR_TYPES[kind]
        self._icon_map = self._description.get(FanAttributes.ICON_MAP)
        self._norm_icon = (
            next(iter(self._icon_map.items()))[1]
            if self._icon_map is not None
            else None
        )
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)
        self._attr_name = (
            f"{name} {self._description[FanAttributes.LABEL].replace('_', ' ').title()}"
        )

        try:
            device_id = self._device_status[PhilipsApi.DEVICE_ID]
            self._attr_unique_id = f"{self._model}-{device_id}-{kind.lower()}"
        except KeyError as e:
            _LOGGER.error("Failed retrieving unique_id: %s", e)
            raise PlatformNotReady from e

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

    @property
    def icon(self) -> str:
        """Return the icon of the binary sensor."""
        icon = self._norm_icon
        if not self._icon_map:
            return icon

        return self._icon_map[self.is_on]
