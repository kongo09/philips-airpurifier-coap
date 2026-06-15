"""Philips Air Purifier & Humidifier fan heater (climate)."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PhilipsApi, PresetMode
from .devices import PhilipsGenericControlBase, collect_class_attribute, model_to_class

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .config_entry_data import ConfigEntryData
    from .const import PhilipsConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PhilipsHeaterEntityDescription(ClimateEntityDescription):
    """Describe a Philips fan heater entity."""

    temperature_key: str
    power_key: str
    on_value: Any
    off_value: Any
    min_temperature: int
    max_temperature: int
    step: float


HEATER_TYPES: tuple[PhilipsHeaterEntityDescription, ...] = (
    PhilipsHeaterEntityDescription(
        key=PhilipsApi.NEW2_TARGET_TEMP,
        temperature_key=PhilipsApi.TEMPERATURE,
        power_key=PhilipsApi.NEW2_POWER,
        on_value=1,
        off_value=0,
        min_temperature=1,
        max_temperature=37,
        step=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhilipsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the climate platform."""
    config_entry_data = entry.runtime_data
    model = config_entry_data.device_information.model

    model_class = model_to_class.get(model)
    if model_class is None:
        _LOGGER.error("Unsupported model: %s", model)
        return

    available_heaters = collect_class_attribute(model_class, "AVAILABLE_HEATERS")
    available_preset_modes: dict[str, Any] = {}
    available_oscillation: dict[str, Any] = {}
    for cls in reversed(model_class.__mro__):
        available_preset_modes.update(getattr(cls, "AVAILABLE_PRESET_MODES", {}))
        oscillation = getattr(cls, "KEY_OSCILLATION", None)
        if oscillation:
            available_oscillation.update(oscillation)

    async_add_entities(
        PhilipsHeater(
            hass,
            entry,
            config_entry_data,
            description,
            available_preset_modes,
            available_oscillation,
        )
        for description in HEATER_TYPES
        if description.key in available_heaters
    )


class PhilipsHeater(PhilipsGenericControlBase, ClimateEntity):
    """Define a Philips AirPurifier fan heater."""

    entity_description: PhilipsHeaterEntityDescription
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO, HVACMode.FAN_ONLY]

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        config_entry_data: ConfigEntryData,
        description: PhilipsHeaterEntityDescription,
        available_preset_modes: dict[str, Any],
        available_oscillation: dict[str, Any],
    ) -> None:
        """Initialize the fan heater."""
        super().__init__(hass, config, config_entry_data)
        self.entity_description = description
        latest_status = config_entry_data.latest_status

        model = config_entry_data.device_information.model
        device_id = config_entry_data.device_information.device_id
        self._attr_unique_id = f"{model}-{device_id}-{description.key.lower()}"

        self._preset_modes = available_preset_modes
        self._attr_preset_modes = list(self._preset_modes.keys())

        self._power_key = description.power_key
        self._temperature_target_key = description.key.partition("#")[0]
        self._current_temperature_key = description.temperature_key

        self._attr_min_temp = description.min_temperature
        self._attr_max_temp = description.max_temperature
        self._attr_target_temperature_step = description.step
        self._attr_target_temperature = latest_status.get(self._temperature_target_key)
        self._attr_current_temperature = latest_status.get(self._current_temperature_key)

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        self._oscillation_key: str | None = None
        self._oscillation_modes: dict[str, Any] = {}
        if available_oscillation:
            self._oscillation_key = next(iter(available_oscillation))
            self._oscillation_modes = available_oscillation[self._oscillation_key]
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            self._attr_swing_modes = [SWING_ON, SWING_OFF]

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._device_status.get(self._temperature_target_key)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device_status.get(self._current_temperature_key)

    @property
    def hvac_mode(self) -> HVACMode:
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
        """Return the current preset mode."""
        for preset_mode, status_pattern in self._preset_modes.items():
            if all(self._device_status.get(k) == v for k, v in status_pattern.items()):
                return preset_mode
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the heater."""
        status_pattern = self._preset_modes.get(preset_mode)
        if status_pattern:
            await self._async_set_control_values(status_pattern)

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        if not self._oscillation_key:
            return None
        if self._device_status.get(self._oscillation_key) == self._oscillation_modes.get("off"):
            return SWING_OFF
        return SWING_ON

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode of the heater."""
        if not self._oscillation_key or swing_mode not in (SWING_ON, SWING_OFF):
            return
        value = self._oscillation_modes["on" if swing_mode == SWING_ON else "off"]
        await self._async_set_control_value(self._oscillation_key, value)

    @property
    def is_on(self) -> bool:
        """Return True if the device is on."""
        return self._device_status.get(self._power_key) != self.entity_description.off_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        await self._async_set_control_value(self._power_key, self.entity_description.on_value)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        await self._async_set_control_value(self._power_key, self.entity_description.off_value)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        target = max(self._attr_min_temp, min(int(temperature), self._attr_max_temp))
        await self._async_set_control_value(self._temperature_target_key, target)
