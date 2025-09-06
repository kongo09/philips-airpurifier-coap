"""Type definitions for Philips AirPurifier integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict
from xmlrpc.client import boolean

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.typing import StateType

DeviceStatus = dict[str, Any]


@dataclass
class DeviceInformation:
    """Device information class."""

    model: str
    name: str
    device_id: str
    host: str
    mac: str | None = None


class _SensorDescription(TypedDict):
    """Mandatory attributes for a sensor description."""

    label: str


class SensorDescription(_SensorDescription, total=False):
    """Sensor description class."""

    # Home Assistant standard attributes using string keys
    device_class: SensorDeviceClass
    state_class: SensorStateClass
    native_unit_of_measurement: str | UnitOfTemperature | UnitOfTime
    entity_category: EntityCategory

    icon: str
    unit: str
    value: Callable[[Any, DeviceStatus], StateType]
    icon_map: list[tuple[int, str]]
    # warn_value: int
    # warn_icon: str


class FilterDescription(TypedDict):
    """Filter description class."""

    prefix: str
    postfix: str
    icon: str
    icon_map: list[tuple[int, str]]
    # warn_icon: str
    # warn_value: int


class SwitchDescription(TypedDict):
    """Switch description class."""

    icon: str
    label: str
    entity_category: str


class LightDescription(TypedDict):
    """Light description class."""

    icon: str
    label: str
    entity_category: str
    switch_on: Any
    switch_off: Any
    dimmable: boolean


class SelectDescription(TypedDict):
    """Select description class."""

    label: str
    entity_category: str
    options: dict[Any, tuple[str, str]]


class NumberDescription(TypedDict):
    """Number class."""

    icon: str
    label: str
    entity_category: str
    unit: str
    off: int
    min: int
    max: int
    step: int


class HumidifierDescription(TypedDict):
    """Humidifier description class."""

    label: str
    humidity: str
    power: str
    on: Any
    off: Any
    function: str
    humidifying: str
    idle: str
    switch: bool
    max_humidity: str
    min_humidity: str


class HeaterDescription(TypedDict):
    """Heater description class."""

    temperature: str
    power: str
    on: Any
    off: Any
    min_temperature: int
    max_temperature: int
    step: int
