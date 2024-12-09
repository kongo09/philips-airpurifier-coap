"""Philips Air Purifier & Humidifier Heater."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.components.climate import (
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .config_entry_data import ConfigEntryData
from .const import (
    DOMAIN,
    HEATER_TYPES,
    SWITCH_OFF,
    SWITCH_ON,
    FanAttributes,
    PresetMode,
)
from .philips import PhilipsGenericControlBase, model_to_class

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up the climate platform."""

    config_entry_data: ConfigEntryData = hass.data[DOMAIN][entry.entry_id]

    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class:
        available_heaters = []
        available_preset_modes = {}
        available_oscillation = {}

        for cls in reversed(model_class.__mro__):
            # Get the available heaters from the base classes
            cls_available_heaters = getattr(cls, "AVAILABLE_HEATERS", [])
            available_heaters.extend(cls_available_heaters)

            # Get the available preset modes from the base classes
            cls_available_preset_modes = getattr(cls, "AVAILABLE_PRESET_MODES", [])
            available_preset_modes.update(cls_available_preset_modes)

            # Get the available oscillation from the base classes
            cls_available_oscillation = getattr(cls, "KEY_OSCILLATION", {})
            _LOGGER.debug("Available oscillation: %s", cls_available_oscillation)
            if cls_available_oscillation:
                available_oscillation.update(cls_available_oscillation)

        heaters = [
            PhilipsHeater(
                hass,
                entry,
                config_entry_data,
                heater,
                available_preset_modes,
                available_oscillation,
            )
            for heater in HEATER_TYPES
            if heater in available_heaters
        ]
        async_add_entities(heaters, update_before_add=False)

    else:
        _LOGGER.error("Unsupported model: %s", model)
        return


class PhilipsHeater(PhilipsGenericControlBase, ClimateEntity):
    """Define a Philips AirPurifier heater."""

    _attr_is_on: bool | None = False
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_hvac_modes: list[HVACMode] = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.AUTO,
        HVACMode.FAN_ONLY,
    ]
    _attr_target_temperature_step: float = 1.0

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        heater: str,
        available_preset_modes: list[str],
        available_oscillation: dict[str, dict[str, Any]],
    ) -> None:
        """Initialize the select."""

        super().__init__(hass, config, config_entry_data)

        self._model = config_entry_data.device_information.model
        latest_status = config_entry_data.latest_status

        self._description = HEATER_TYPES[heater]

        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{self._model}-{device_id}-{heater.lower()}"

        # preset modes in the climate entity are used for HVAC, so we use fan modes
        self._preset_modes = available_preset_modes
        self._attr_preset_modes = list(self._preset_modes.keys())

        self._power_key = self._description[FanAttributes.POWER]
        self._temperature_target_key = heater.partition("#")[0]

        self._attr_min_temp = self._description[FanAttributes.MIN_TEMPERATURE]
        self._attr_max_temp = self._description[FanAttributes.MAX_TEMPERATURE]
        self._attr_target_temperature = latest_status.get(self._temperature_target_key)
        self._attr_current_temperature = latest_status.get(
            self._description[FanAttributes.TEMPERATURE]
        )

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        # some devices can oscillate
        if available_oscillation:
            self._oscillation_key = list(available_oscillation.keys())[0]
            self._oscillation_modes = available_oscillation[self._oscillation_key]
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            self._attr_swing_modes = [SWING_ON, SWING_OFF]

    @property
    def target_temperature(self) -> int | None:
        """Return the target temperature."""
        return self._device_status.get(self._temperature_target_key)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        if not self.is_on:
            return HVACMode.OFF
        if self.preset_mode == PresetMode.AUTO:
            return HVACMode.AUTO
        if self.preset_mode == PresetMode.VENTILATION:
            return HVACMode.FAN_ONLY
        return HVACMode.HEAT

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode of the heater."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.AUTO:
            await self.async_set_preset_mode(PresetMode.AUTO)
        elif hvac_mode == HVACMode.FAN_ONLY:
            await self.async_set_preset_mode(PresetMode.VENTILATION)
        elif hvac_mode == HVACMode.HEAT:
            await self.async_set_preset_mode(PresetMode.LOW)

    @property
    def preset_mode(self) -> str | None:
        """Return the current fan mode."""

        for fan_mode, status_pattern in self._preset_modes.items():
            for k, v in status_pattern.items():
                status = self._device_status.get(k)
                if status != v:
                    break
            else:
                return fan_mode

        # no mode found
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the fan mode of the heater."""
        if preset_mode not in self._attr_preset_modes:
            return

        status_pattern = self._preset_modes.get(preset_mode)
        await self.coordinator.client.set_control_values(data=status_pattern)
        self._device_status.update(status_pattern)
        self._handle_coordinator_update()

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        if not self._oscillation_key:
            return None

        value = self._device_status.get(self._oscillation_key)
        if value == self._oscillation_modes[SWITCH_OFF]:
            return SWING_OFF

        return SWING_ON

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode of the heater."""
        if swing_mode not in self._attr_swing_modes:
            return

        if swing_mode == SWING_ON:
            value = self._oscillation_modes[SWITCH_ON]
        else:
            value = self._oscillation_modes[SWITCH_OFF]

        await self.coordinator.client.set_control_value(self._oscillation_key, value)
        self._device_status[self._oscillation_key] = value
        self._handle_coordinator_update()

    @property
    def is_on(self) -> bool | None:
        """Return the device state."""
        if (
            self._device_status.get(self._power_key)
            == self._description[FanAttributes.OFF]
        ):
            return False

        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        await self.coordinator.client.set_control_values(
            data={
                self._power_key: self._description[FanAttributes.ON],
            }
        )
        self._device_status[self._power_key] = self._description[FanAttributes.ON]
        self._handle_coordinator_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self.coordinator.client.set_control_values(
            data={
                self._power_key: self._description[FanAttributes.OFF],
            }
        )
        self._device_status[self._power_key] = self._description[FanAttributes.OFF]
        self._handle_coordinator_update()

    async def async_set_temperature(self, **kwargs) -> None:
        """Select target temperature."""
        temperature = int(kwargs.get(ATTR_TEMPERATURE))

        target = max(self._attr_min_temp, min(temperature, self._attr_max_temp))
        await self.coordinator.client.set_control_value(
            self._temperature_target_key, target
        )
        self._device_status[self._temperature_target_key] = temperature
        self._handle_coordinator_update()
