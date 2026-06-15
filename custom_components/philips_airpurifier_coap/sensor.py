"""Philips Air Purifier & Humidifier sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import ICON, FanAttributes, PhilipsApi
from .devices import PhilipsEntity, collect_class_attribute, model_to_class

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .config_entry_data import ConfigEntryData
    from .const import PhilipsConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

IconMap = tuple[tuple[float, str], ...]


def _icon_from_map(value: Any, icon_map: IconMap | None) -> str | None:
    """Pick the icon for ``value`` from an ascending (level, icon) map."""
    if not icon_map:
        return None
    icon = icon_map[0][1]
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return icon
    for level, level_icon in icon_map:
        if numeric >= level:
            icon = level_icon
    return icon


@dataclass(frozen=True, kw_only=True)
class PhilipsSensorEntityDescription(SensorEntityDescription):
    """Describe a Philips sensor entity."""

    value_fn: Callable[[Any, dict], StateType] | None = None
    icon_map: IconMap | None = None


@dataclass(frozen=True, kw_only=True)
class PhilipsFilterEntityDescription(SensorEntityDescription):
    """Describe a Philips filter sensor entity."""

    icon_map: IconMap | None = None
    total_key: str = ""
    type_key: str = ""


SENSOR_TYPES: tuple[PhilipsSensorEntityDescription, ...] = (
    PhilipsSensorEntityDescription(
        key=PhilipsApi.INDOOR_ALLERGEN_INDEX,
        translation_key=FanAttributes.INDOOR_ALLERGEN_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.NEW_INDOOR_ALLERGEN_INDEX,
        translation_key=FanAttributes.INDOOR_ALLERGEN_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.NEW2_INDOOR_ALLERGEN_INDEX,
        translation_key=FanAttributes.INDOOR_ALLERGEN_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.PM25,
        device_class=SensorDeviceClass.PM25,
        translation_key=FanAttributes.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.NEW_PM25,
        device_class=SensorDeviceClass.PM25,
        translation_key=FanAttributes.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.NEW2_PM25,
        device_class=SensorDeviceClass.PM25,
        translation_key=FanAttributes.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.NEW2_GAS,
        translation_key=FanAttributes.GAS,
        native_unit_of_measurement="L",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.TOTAL_VOLATILE_ORGANIC_COMPOUNDS,
        translation_key=FanAttributes.TOTAL_VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement="L",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        translation_key=FanAttributes.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.NEW2_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        translation_key=FanAttributes.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.NEW2_REMAINING_TIME,
        device_class=SensorDeviceClass.DURATION,
        translation_key=FanAttributes.TIME_REMAINING,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        translation_key=FanAttributes.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon_map=(
            (0, "mdi:thermometer-low"),
            (17, "mdi:thermometer"),
            (23, "mdi:thermometer-high"),
        ),
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.NEW2_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        translation_key=FanAttributes.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda value, _: value / 10,
        icon_map=(
            (0, "mdi:thermometer-low"),
            (17, "mdi:thermometer"),
            (23, "mdi:thermometer-high"),
        ),
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.WATER_LEVEL,
        translation_key=FanAttributes.WATER_LEVEL,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value, status: (
            0 if status.get(PhilipsApi.ERROR_CODE) in (32768, 49408) else value
        ),
        icon_map=((0, ICON.WATER_REFILL), (10, "mdi:water")),
    ),
    PhilipsSensorEntityDescription(
        key=PhilipsApi.RSSI,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        translation_key=FanAttributes.RSSI,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon_map=(
            (-150, "mdi:wifi-strength-off-outline"),
            (-90, "mdi:wifi-strength-outline"),
            (-80, "mdi:wifi-strength-1"),
            (-70, "mdi:wifi-strength-2"),
            (-67, "mdi:wifi-strength-3"),
            (-30, "mdi:wifi-strength-4"),
        ),
    ),
)


FILTER_TYPES: tuple[PhilipsFilterEntityDescription, ...] = (
    PhilipsFilterEntityDescription(
        key=PhilipsApi.FILTER_PRE,
        translation_key=FanAttributes.FILTER_PRE,
        icon_map=((0, ICON.FILTER_REPLACEMENT), (72, "mdi:dots-grid")),
        total_key=PhilipsApi.FILTER_PRE_TOTAL,
        type_key=PhilipsApi.FILTER_PRE_TYPE,
    ),
    PhilipsFilterEntityDescription(
        key=PhilipsApi.FILTER_HEPA,
        translation_key=FanAttributes.FILTER_HEPA,
        icon_map=((0, ICON.FILTER_REPLACEMENT), (72, "mdi:dots-grid")),
        total_key=PhilipsApi.FILTER_HEPA_TOTAL,
        type_key=PhilipsApi.FILTER_HEPA_TYPE,
    ),
    PhilipsFilterEntityDescription(
        key=PhilipsApi.FILTER_ACTIVE_CARBON,
        translation_key=FanAttributes.FILTER_ACTIVE_CARBON,
        icon_map=((0, ICON.FILTER_REPLACEMENT), (72, "mdi:dots-grid")),
        total_key=PhilipsApi.FILTER_ACTIVE_CARBON_TOTAL,
        type_key=PhilipsApi.FILTER_ACTIVE_CARBON_TYPE,
    ),
    PhilipsFilterEntityDescription(
        key=PhilipsApi.FILTER_WICK,
        translation_key=FanAttributes.FILTER_WICK,
        icon_map=((0, ICON.PREFILTER_WICK_CLEANING), (72, "mdi:dots-grid")),
        total_key=PhilipsApi.FILTER_WICK_TOTAL,
        type_key=PhilipsApi.FILTER_WICK_TYPE,
    ),
    PhilipsFilterEntityDescription(
        key=PhilipsApi.FILTER_NANOPROTECT,
        translation_key=FanAttributes.FILTER_NANOPROTECT,
        icon_map=((0, ICON.FILTER_REPLACEMENT), (10, ICON.NANOPROTECT_FILTER)),
        total_key=PhilipsApi.FILTER_NANOPROTECT_TOTAL,
        type_key=PhilipsApi.FILTER_NANOPROTECT_TYPE,
    ),
    PhilipsFilterEntityDescription(
        key=PhilipsApi.FILTER_NANOPROTECT_PREFILTER,
        translation_key=FanAttributes.FILTER_NANOPROTECT_CLEAN,
        icon_map=((0, ICON.PREFILTER_CLEANING), (10, ICON.NANOPROTECT_FILTER)),
        total_key=PhilipsApi.FILTER_NANOPROTECT_CLEAN_TOTAL,
        type_key="",
    ),
    PhilipsFilterEntityDescription(
        key=PhilipsApi.NEW2_FILTER_NANOPROTECT,
        translation_key=FanAttributes.FILTER_NANOPROTECT,
        icon_map=((0, ICON.FILTER_REPLACEMENT), (10, ICON.NANOPROTECT_FILTER)),
        total_key=PhilipsApi.NEW2_FILTER_NANOPROTECT_TOTAL,
        type_key="",
    ),
    PhilipsFilterEntityDescription(
        key=PhilipsApi.NEW2_FILTER_NANOPROTECT_PREFILTER,
        translation_key=FanAttributes.FILTER_NANOPROTECT_CLEAN,
        icon_map=((0, ICON.PREFILTER_CLEANING), (10, ICON.NANOPROTECT_FILTER)),
        total_key=PhilipsApi.NEW2_FILTER_NANOPROTECT_PREFILTER_TOTAL,
        type_key="",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhilipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    config_entry_data = entry.runtime_data
    model = config_entry_data.device_information.model
    status = config_entry_data.latest_status or {}

    model_class = model_to_class.get(model)
    unavailable_sensors = []
    unavailable_filters = []
    if model_class:
        unavailable_sensors = collect_class_attribute(model_class, "UNAVAILABLE_SENSORS")
        unavailable_filters = collect_class_attribute(model_class, "UNAVAILABLE_FILTERS")

    entities: list[SensorEntity] = [
        PhilipsSensor(hass, entry, config_entry_data, description)
        for description in SENSOR_TYPES
        if description.key in status and description.key not in unavailable_sensors
    ]
    entities.extend(
        PhilipsFilterSensor(hass, entry, config_entry_data, description)
        for description in FILTER_TYPES
        if description.key in status and description.key not in unavailable_filters
    )

    async_add_entities(entities)


class PhilipsSensor(PhilipsEntity, SensorEntity):
    """Define a Philips AirPurifier sensor."""

    entity_description: PhilipsSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        description: PhilipsSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, config, config_entry_data)
        self.entity_description = description

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{description.key.lower()}"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        value = self._device_status.get(self.entity_description.key)
        if value is None:
            return None
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(value, self._device_status)
        return value

    @property
    def icon(self) -> str | None:
        """Return the icon of the sensor."""
        return _icon_from_map(self.native_value, self.entity_description.icon_map)


class PhilipsFilterSensor(PhilipsEntity, SensorEntity):
    """Define a Philips AirPurifier filter sensor."""

    entity_description: PhilipsFilterEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        description: PhilipsFilterEntityDescription,
    ) -> None:
        """Initialize the filter sensor."""
        super().__init__(hass, config, config_entry_data)
        self.entity_description = description

        self._value_key = description.key
        self._total_key = description.total_key
        self._type_key = description.type_key

        if self._has_total:
            self._attr_native_unit_of_measurement = PERCENTAGE
        else:
            self._attr_native_unit_of_measurement = UnitOfTime.HOURS

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{description.translation_key}"

    @property
    def native_value(self) -> StateType:
        """Return the native value of the filter sensor."""
        if self._has_total:
            return self._percentage
        return self._time_remaining

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the extra state attributes of the filter sensor."""
        attrs: dict[str, Any] = {}
        if self._type_key and self._type_key in self._device_status:
            attrs[FanAttributes.TYPE] = self._device_status[self._type_key]
        if self._has_total:
            attrs[FanAttributes.TOTAL] = self._total
            attrs[FanAttributes.TIME_REMAINING] = self._time_remaining
        return attrs

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
    def icon(self) -> str | None:
        """Return the icon of the filter sensor."""
        return _icon_from_map(self.native_value, self.entity_description.icon_map)
