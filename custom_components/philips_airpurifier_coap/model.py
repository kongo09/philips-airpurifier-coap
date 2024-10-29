"""Type definitions for Philips AirPurifier integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict
from xmlrpc.client import boolean

from homeassistant.helpers.typing import StateType

DeviceStatus = dict[str, Any]


class _SensorDescription(TypedDict):
    """Mandatory attributes for a sensor description."""

    label: str


class SensorDescription(_SensorDescription, total=False):
    """Sensor description class."""

    device_class: str
    icon: str
    unit: str
    state_class: str
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
