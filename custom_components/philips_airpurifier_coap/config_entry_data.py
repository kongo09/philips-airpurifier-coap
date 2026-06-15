"""Module containing the ConfigEntryData class for the Philips Air Purifier integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aioairctrl import CoAPClient

    from .coordinator import Coordinator
    from .model import DeviceInformation, DeviceStatus


@dataclass(slots=True)
class ConfigEntryData:
    """Runtime data for a Philips AirPurifier config entry."""

    device_information: DeviceInformation
    client: CoAPClient
    coordinator: Coordinator
    latest_status: DeviceStatus | None = field(default=None)
