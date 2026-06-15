"""Type definitions for Philips AirPurifier integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DeviceStatus = dict[str, Any]


@dataclass
class DeviceInformation:
    """Device information class."""

    model: str
    name: str
    device_id: str
    host: str
    mac: str | None = None
