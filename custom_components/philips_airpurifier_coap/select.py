"""Philips Air Purifier & Humidifier Selects."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.select import SelectEntity
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
    CONF_MODEL,
    DATA_KEY_COORDINATOR,
    DOMAIN,
    OPTIONS,
    SELECT_TYPES,
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
    """Set up the select platform."""
    _LOGGER.debug("async_setup_entry called for platform select")

    host = entry.data[CONF_HOST]
    model = entry.data[CONF_MODEL]
    name = entry.data[CONF_NAME]

    data = hass.data[DOMAIN][host]

    coordinator = data[DATA_KEY_COORDINATOR]

    model_class = model_to_class.get(model)
    if model_class:
        available_selects = []

        for cls in reversed(model_class.__mro__):
            cls_available_selects = getattr(cls, "AVAILABLE_SELECTS", [])
            available_selects.extend(cls_available_selects)

        selects = [
            PhilipsSelect(coordinator, name, model, select)
            for select in SELECT_TYPES
            if select in available_selects
        ]

        async_add_entities(selects, update_before_add=False)

    else:
        _LOGGER.error("Unsupported model: %s", model)
        return


class PhilipsSelect(PhilipsEntity, SelectEntity):
    """Define a Philips AirPurifier select."""

    _attr_is_on: bool | None = False

    def __init__(  # noqa: D107
        self, coordinator: Coordinator, name: str, model: str, select: str
    ) -> None:
        super().__init__(coordinator)
        self._model = model
        self._description = SELECT_TYPES[select]
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        label = FanAttributes.LABEL
        label = label.partition("#")[0]
        self._attr_name = f"{name} {self._description[label].replace('_', ' ').title()}"
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)

        self._attr_options = []
        self._icons = {}
        self._options = {}
        options = self._description.get(OPTIONS)
        for key, option_tuple in options.items():
            option_name, icon = option_tuple
            self._attr_options.append(option_name)
            self._icons[option_name] = icon
            self._options[key] = option_name

        try:
            device_id = self._device_status[PhilipsApi.DEVICE_ID]
            self._attr_unique_id = f"{self._model}-{device_id}-{select.lower()}"
        except KeyError as e:
            _LOGGER.error("Failed retrieving unique_id due to missing key: %s", e)
            raise PlatformNotReady from e
        except TypeError as e:
            _LOGGER.error("Failed retrieving unique_id due to type error: %s", e)
            raise PlatformNotReady from e

        self._attrs: dict[str, Any] = {}
        self.kind = select.partition("#")[0]

    @property
    def current_option(self) -> str:
        """Return the currently selected option."""
        option = self._device_status.get(self.kind)
        _LOGGER.debug("current_option: %s", option)
        if option in self._options:
            return self._options[option]
        return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option is None or len(option) == 0:
            _LOGGER.error("Cannot set empty option '%s'", option)
            return
        try:
            option_key = next(
                key for key, value in self._options.items() if value == option
            )
            _LOGGER.debug(
                "async_selection_option, kind: %s - option: %s - value: %s",
                self.kind,
                option,
                option_key,
            )
            await self.coordinator.client.set_control_value(self.kind, option_key)
        except KeyError as e:
            _LOGGER.error("Invalid option key: '%s' with error: %s", option, e)
        except ValueError as e:
            _LOGGER.error("Invalid value for option: '%s' with error: %s", option, e)

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icons.get(self.current_option)
