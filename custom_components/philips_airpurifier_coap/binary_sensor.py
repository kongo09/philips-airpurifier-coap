"""Philips Air Purifier & Humidifier binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_FILTER_ALERT_THRESHOLD,
    DEFAULT_FILTER_ALERT_THRESHOLD,
    FanAttributes,
    PhilipsApi,
)
from .devices import PhilipsEntity, collect_class_attribute, model_to_class
from .sensor import FILTER_TYPES

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .config_entry_data import ConfigEntryData
    from .const import PhilipsConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

EVENT_FILTER_ALERT = "philips_filter_alert"

_FILTER_BY_KEY = {description.key: description for description in FILTER_TYPES}


@dataclass(frozen=True, kw_only=True)
class PhilipsBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Philips binary sensor entity."""

    value_fn: Callable[[Any], bool] | None = None


BINARY_SENSOR_TYPES: tuple[PhilipsBinarySensorEntityDescription, ...] = (
    PhilipsBinarySensorEntityDescription(
        # the out-of-water error is encoded in bit 9 of the error number
        key=PhilipsApi.ERROR_CODE,
        translation_key=FanAttributes.WATER_TANK,
        device_class=BinarySensorDeviceClass.MOISTURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: not value & (1 << 8),
    ),
    PhilipsBinarySensorEntityDescription(
        key=PhilipsApi.NEW2_ERROR_CODE,
        translation_key=FanAttributes.WATER_TANK,
        device_class=BinarySensorDeviceClass.MOISTURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda value: not value & (1 << 8),
    ),
    PhilipsBinarySensorEntityDescription(
        # the water container being present means humidification is on
        key=PhilipsApi.FUNCTION,
        translation_key=FanAttributes.HUMIDIFICATION,
        value_fn=lambda value: value == "PH",
    ),
    PhilipsBinarySensorEntityDescription(
        key=PhilipsApi.NEW2_MODE_A,
        translation_key=FanAttributes.HUMIDIFICATION,
        value_fn=lambda value: value == 4,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhilipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    config_entry_data = entry.runtime_data
    model = config_entry_data.device_information.model
    status = config_entry_data.latest_status or {}

    model_class = model_to_class.get(model)
    available_binary_sensors = []
    unavailable_filters = []
    if model_class:
        available_binary_sensors = collect_class_attribute(model_class, "AVAILABLE_BINARY_SENSORS")
        unavailable_filters = collect_class_attribute(model_class, "UNAVAILABLE_FILTERS")

    entities: list[BinarySensorEntity] = [
        PhilipsBinarySensor(hass, entry, config_entry_data, description)
        for description in BINARY_SENSOR_TYPES
        if description.key in status and description.key in available_binary_sensors
    ]

    # Add a single filter-alert sensor when the device exposes any filter.
    available_filters = [
        description.key
        for description in FILTER_TYPES
        if description.key in status and description.key not in unavailable_filters
    ]
    if available_filters:
        entities.append(PhilipsFilterAlertSensor(hass, entry, config_entry_data, available_filters))

    async_add_entities(entities)


class PhilipsBinarySensor(PhilipsEntity, BinarySensorEntity):
    """Define a Philips AirPurifier binary sensor."""

    entity_description: PhilipsBinarySensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        description: PhilipsBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(hass, config, config_entry_data)
        self.entity_description = description

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{description.key.lower()}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        value = self._device_status.get(self.entity_description.key)
        if value is None:
            return None
        if self.entity_description.value_fn is not None:
            return bool(self.entity_description.value_fn(value))
        return bool(value)


class PhilipsFilterAlertSensor(PhilipsEntity, BinarySensorEntity):
    """Binary sensor that indicates if any filter needs attention."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = FanAttributes.FILTER_NEEDS_ATTENTION

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        filter_keys: list[str],
    ) -> None:
        """Initialize the filter alert sensor."""
        super().__init__(hass, config, config_entry_data)

        self._filter_keys = filter_keys
        self._previous_alert_state: bool | None = None
        self._previous_low_filters: set[str] = set()
        self._threshold = config.options.get(
            CONF_FILTER_ALERT_THRESHOLD, DEFAULT_FILTER_ALERT_THRESHOLD
        )

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-filter_alert"

    @property
    def is_on(self) -> bool:
        """Return True if any filter needs attention (below threshold)."""
        return bool(self._get_low_filters())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes with details about low filters."""
        low_filters = self._get_low_filters()
        attrs: dict[str, Any] = {
            "threshold": self._threshold,
            "low_filters": list(low_filters.keys()),
        }
        for filter_key, percentage in low_filters.items():
            attrs[f"{self._filter_name(filter_key)}_percentage"] = percentage
        return attrs

    @staticmethod
    def _filter_name(filter_key: str) -> str:
        """Return the translation key (display name) of a filter."""
        description = _FILTER_BY_KEY.get(filter_key)
        return description.translation_key if description else filter_key

    def _get_low_filters(self) -> dict[str, float]:
        """Get filters that are below the threshold with their percentages."""
        low_filters: dict[str, float] = {}
        for filter_key in self._filter_keys:
            if filter_key not in self._device_status:
                continue

            description = _FILTER_BY_KEY.get(filter_key)
            if description is None:
                continue

            value = self._device_status[filter_key]
            total_key = description.total_key
            if total_key and total_key in self._device_status:
                total = self._device_status[total_key]
                if total > 0:
                    percentage = round(100.0 * value / total)
                    if percentage < self._threshold:
                        low_filters[filter_key] = percentage
            elif value < 72:
                # No total available: use the raw hours value (~3 days).
                low_filters[filter_key] = value
        return low_filters

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator and fire events."""
        current_low_filters = set(self._get_low_filters().keys())

        # Fire an event when a new filter drops below the threshold.
        if self._previous_alert_state is not None:
            low_filters_data = self._get_low_filters()
            for filter_key in current_low_filters - self._previous_low_filters:
                filter_name = self._filter_name(filter_key)
                device_info = self.config_entry_data.device_information
                self.hass.bus.fire(
                    EVENT_FILTER_ALERT,
                    {
                        "device_id": device_info.device_id,
                        "device_name": device_info.name,
                        "filter_key": filter_key,
                        "filter_name": filter_name,
                        "percentage": low_filters_data.get(filter_key),
                        "threshold": self._threshold,
                    },
                )
                _LOGGER.info(
                    "Filter alert: %s is at %s%% (threshold: %s%%)",
                    filter_name,
                    low_filters_data.get(filter_key),
                    self._threshold,
                )

        self._previous_alert_state = bool(current_low_filters)
        self._previous_low_filters = current_low_filters
        super()._handle_coordinator_update()
