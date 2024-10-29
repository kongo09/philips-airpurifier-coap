"""Philips Air Purifier & Humidifier Switches."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    SWITCH_OFF,
    SWITCH_ON,
    SWITCH_TYPES,
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
    """Set up platform for switch."""
    _LOGGER.debug("async_setup_entry called for platform switch")

    host = entry.data[CONF_HOST]
    model = entry.data[CONF_MODEL]
    name = entry.data[CONF_NAME]

    data = hass.data[DOMAIN][host]

    coordinator = data[DATA_KEY_COORDINATOR]

    model_class = model_to_class.get(model)
    if model_class:
        available_switches = []

        for cls in reversed(model_class.__mro__):
            cls_available_switches = getattr(cls, "AVAILABLE_SWITCHES", [])
            available_switches.extend(cls_available_switches)

        switches = [
            PhilipsSwitch(coordinator, name, model, switch)
            for switch in SWITCH_TYPES
            if switch in available_switches
        ]

        async_add_entities(switches, update_before_add=False)

    else:
        _LOGGER.error("Unsupported model: %s", model)
        return


class PhilipsSwitch(PhilipsEntity, SwitchEntity):
    """Define a Philips AirPurifier switch."""

    _attr_is_on: bool | None = False

    def __init__(  # noqa: D107
        self, coordinator: Coordinator, name: str, model: str, switch: str
    ) -> None:
        super().__init__(coordinator)
        self._model = model
        self._description = SWITCH_TYPES[switch]
        self._on = self._description.get(SWITCH_ON)
        self._off = self._description.get(SWITCH_OFF)
        self._attr_device_class = self._description.get(ATTR_DEVICE_CLASS)
        self._attr_icon = self._description.get(ATTR_ICON)
        self._attr_name = (
            f"{name} {self._description[FanAttributes.LABEL].replace('_', ' ').title()}"
        )
        self._attr_entity_category = self._description.get(CONF_ENTITY_CATEGORY)

        try:
            device_id = self._device_status[PhilipsApi.DEVICE_ID]
            self._attr_unique_id = f"{self._model}-{device_id}-{switch.lower()}"
        except KeyError as e:
            _LOGGER.error("Failed retrieving unique_id: %s", e)
            raise PlatformNotReady from e

        self._attrs: dict[str, Any] = {}
        self.kind = switch

    @property
    def is_on(self) -> bool:
        """Return if switch is on."""
        return self._device_status.get(self.kind) == self._on

    async def async_turn_on(self, **kwargs) -> None:
        """Switch the switch on."""
        _LOGGER.debug("async_turn_on, kind: %s - value: %s", self.kind, self._on)
        await self.coordinator.client.set_control_value(self.kind, self._on)

    async def async_turn_off(self, **kwargs) -> None:
        """Switch the switch off."""
        _LOGGER.debug("async_turn_off, kind: %s - value: %s", self.kind, self._off)
        await self.coordinator.client.set_control_value(self.kind, self._off)
