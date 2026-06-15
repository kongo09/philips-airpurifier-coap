"""Philips Air Purifier & Humidifier selects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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
class PhilipsSelectEntityDescription(SelectEntityDescription):
    """Describe a Philips select entity."""

    options_map: Mapping[Any, str]


SELECT_TYPES: tuple[PhilipsSelectEntityDescription, ...] = (
    PhilipsSelectEntityDescription(
        key=PhilipsApi.FUNCTION,
        translation_key=FanAttributes.FUNCTION,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.FUNCTION_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW2_LAMP_MODE,
        translation_key=FanAttributes.LAMP_MODE,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.LAMP_MODE_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW2_LAMP_MODE2,
        translation_key=FanAttributes.LAMP_MODE,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.LAMP_MODE_MAP2,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW2_AMBIENT_LIGHT_MODE,
        translation_key=FanAttributes.AMBIENT_LIGHT_MODE,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.AMBIENT_LIGHT_MODE_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.PREFERRED_INDEX,
        translation_key=FanAttributes.PREFERRED_INDEX,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.PREFERRED_INDEX_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW_PREFERRED_INDEX,
        translation_key=FanAttributes.PREFERRED_INDEX,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.NEW_PREFERRED_INDEX_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW2_PREFERRED_INDEX,
        translation_key=FanAttributes.PREFERRED_INDEX,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.NEW2_PREFERRED_INDEX_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.GAS_PREFERRED_INDEX,
        translation_key=FanAttributes.PREFERRED_INDEX,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.GAS_PREFERRED_INDEX_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW2_GAS_PREFERRED_INDEX,
        translation_key=FanAttributes.PREFERRED_INDEX,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.NEW2_GAS_PREFERRED_INDEX_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW2_CIRCULATION,
        translation_key=FanAttributes.FUNCTION,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.CIRCULATION_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW2_HEATING,
        translation_key=FanAttributes.FUNCTION,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.HEATING_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW2_TIMER,
        translation_key=FanAttributes.TIMER,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.TIMER_MAP,
    ),
    PhilipsSelectEntityDescription(
        key=PhilipsApi.NEW2_TIMER2,
        translation_key=FanAttributes.TIMER,
        entity_category=EntityCategory.CONFIG,
        options_map=PhilipsApi.TIMER2_MAP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhilipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform."""
    config_entry_data = entry.runtime_data
    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class is None:
        _LOGGER.error("Unsupported model: %s", model)
        return

    available_selects = collect_class_attribute(model_class, "AVAILABLE_SELECTS")
    async_add_entities(
        PhilipsSelect(hass, entry, config_entry_data, description)
        for description in SELECT_TYPES
        if description.key in available_selects
    )


class PhilipsSelect(PhilipsEntity, SelectEntity):
    """Define a Philips AirPurifier select."""

    entity_description: PhilipsSelectEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        description: PhilipsSelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(hass, config, config_entry_data)
        self.entity_description = description

        self._options = dict(description.options_map)
        self._attr_options = list(self._options.values())

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{description.key.lower()}"

        # Some Philips keys are disambiguated with a "#" marker that is not part
        # of the actual device payload key.
        self._key = description.key.partition("#")[0]

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option, or None if unknown."""
        return self._options.get(self._device_status.get(self._key))

    async def async_select_option(self, option: str) -> None:
        """Select a new option."""
        try:
            option_key = next(key for key, value in self._options.items() if value == option)
        except StopIteration:
            _LOGGER.error("Invalid option '%s' for %s", option, self._key)
            return

        await self._async_set_control_value(self._key, option_key)
