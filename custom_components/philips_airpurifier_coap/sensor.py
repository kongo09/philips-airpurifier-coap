"""Philips Air Purifier & Humidifier Sensors."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any, cast

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_HOST,
    CONF_NAME,
    PERCENTAGE,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity, EntityCategory
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_MODEL,
    DATA_KEY_COORDINATOR,
    DOMAIN,
    EXTRA_SENSOR_TYPES,
    FILTER_TYPES,
    SENSOR_TYPES,
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
    _LOGGER.debug("async_setup_entry called for platform sensor")

    host = entry.data[CONF_HOST]
    model = entry.data[CONF_MODEL]
    name = entry.data[CONF_NAME]

    data = hass.data[DOMAIN][host]

    coordinator = data[DATA_KEY_COORDINATOR]
    status = coordinator.status

    model_class = model_to_class.get(model)
    unavailable_filters = []
    unavailable_sensors = []
    extra_sensors = []

    if model_class:
        for cls in reversed(model_class.__mro__):
            cls_unavailable_filters = getattr(cls, "UNAVAILABLE_FILTERS", [])
            unavailable_filters.extend(cls_unavailable_filters)
            cls_unavailable_sensors = getattr(cls, "UNAVAILABLE_SENSORS", [])
            unavailable_sensors.extend(cls_unavailable_sensors)
            cls_extra_sensors = getattr(cls, "EXTRA_SENSORS", [])
            extra_sensors.extend(cls_extra_sensors)

    sensors = []

    for sensor in SENSOR_TYPES:
        if sensor in status and sensor not in unavailable_sensors:
            sensors.append(PhilipsSensor(coordinator, name, model, sensor))

    for sensor in EXTRA_SENSOR_TYPES:
        if sensor in status and sensor in extra_sensors:
            sensors.append(PhilipsSensor(coordinator, name, model, sensor))

    for _filter in FILTER_TYPES:
        if _filter in status and _filter not in unavailable_filters:
            sensors.append(PhilipsFilterSensor(coordinator, name, model, _filter))

    async_add_entities(sensors, update_before_add=False)


class PhilipsSensor(PhilipsEntity, SensorEntity):
    """Define a Philips AirPurifier sensor."""

    def __init__(  # noqa: D107
        self, coordinator: Coordinator, name: str, model: str, kind: str
    ) -> None:
        super().__init__(coordinator)
        self._model = model

        # the sensor could be a normal sensor or an extra sensor
        if kind in SENSOR_TYPES:
            self._description = SENSOR_TYPES[kind]
        else:
            self._description = EXTRA_SENSOR_TYPES[kind]

        self._icon_map = self._description.get(FanAttributes.ICON_MAP)
        self._norm_icon = (
            next(iter(self._icon_map.items()))[1]
            if self._icon_map is not None
            else None
        )
        self._attr_state_class = self._description.get(ATTR_STATE_CLASS)
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)
        self._attr_name = (
            f"{name} {self._description[FanAttributes.LABEL].replace('_', ' ').title()}"
        )
        self._attr_native_unit_of_measurement = self._description.get(
            FanAttributes.UNIT
        )

        try:
            device_id = self._device_status[PhilipsApi.DEVICE_ID]
            self._attr_unique_id = f"{self._model}-{device_id}-{kind.lower()}"
        except Exception as e:
            _LOGGER.error("Failed retrieving unique_id: %s", e)
            raise PlatformNotReady
        self._attrs: dict[str, Any] = {}
        self.kind = kind

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        value = self._device_status[self.kind]
        convert = self._description.get(FanAttributes.VALUE)
        if convert:
            value = convert(value, self._device_status)
        return cast(StateType, value)

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        icon = self._norm_icon
        if not self._icon_map:
            return icon

        value = int(self.native_value)
        for level_value, level_icon in self._icon_map.items():
            if value >= level_value:
                icon = level_icon
        return icon


class PhilipsFilterSensor(PhilipsEntity, SensorEntity):
    """Define a Philips AirPurifier filter sensor."""

    def __init__(  # noqa: D107
        self, coordinator: Coordinator, name: str, model: str, kind: str
    ) -> None:
        super().__init__(coordinator)
        self._model = model
        self._description = FILTER_TYPES[kind]
        self._icon_map = self._description[FanAttributes.ICON_MAP]
        self._norm_icon = (
            next(iter(self._icon_map.items()))[1]
            if self._icon_map is not None
            else None
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_name = (
            f"{name} {self._description[FanAttributes.LABEL].replace('_', ' ').title()}"
        )

        self._value_key = kind
        self._total_key = self._description[FanAttributes.TOTAL]
        self._type_key = self._description[FanAttributes.TYPE]

        if self._has_total:
            self._attr_native_unit_of_measurement = PERCENTAGE
        else:
            self._attr_native_unit_of_measurement = UnitOfTime.HOURS

        try:
            device_id = self._device_status[PhilipsApi.DEVICE_ID]
            self._attr_unique_id = (
                f"{self._model}-{device_id}-{self._description[FanAttributes.LABEL]}"
            )
        except Exception as e:
            _LOGGER.error("Failed retrieving unique_id: %s", e)
            raise PlatformNotReady
        self._attrs: dict[str, Any] = {}

    @property
    def native_value(self) -> StateType:
        """Return the native value of the filter sensor."""
        if self._has_total:
            return self._percentage
        else:
            return self._time_remaining

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the extra state attributes of the filter sensor."""
        if self._type_key in self._device_status:
            self._attrs[FanAttributes.TYPE] = self._device_status[self._type_key]
        # self._attrs[ATTR_RAW] = self._value
        if self._has_total:
            self._attrs[FanAttributes.TOTAL] = self._total
            self._attrs[FanAttributes.TIME_REMAINING] = self._time_remaining
        return self._attrs

    @property
    def _has_total(self) -> bool:
        return self._total_key in self._device_status

    @property
    def _percentage(self) -> float:
        return round(100.0 * self._value / self._total)

    @property
    def _time_remaining(self) -> str:
        return str(round(timedelta(hours=self._value) / timedelta(hours=1)))

    @property
    def _value(self) -> int:
        return self._device_status[self._value_key]

    @property
    def _total(self) -> int:
        return self._device_status[self._total_key]

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        icon = self._norm_icon
        if not self._icon_map:
            return icon

        value = int(self.native_value)
        for level_value, level_icon in self._icon_map.items():
            if value >= level_value:
                icon = level_icon
        return icon
