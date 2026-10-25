"""Module containing the ConfigEntryData class for the Philips Air Purifier integration."""

from dataclasses import dataclass

from aioairctrl import CoAPClient

from .coordinator import Coordinator
from .model import DeviceInformation, DeviceStatus
from .status_recovery import StatusRecoveryClient


@dataclass
class ConfigEntryData:
    """Config entry data class."""

    device_information: DeviceInformation
    client: CoAPClient | StatusRecoveryClient
    coordinator: Coordinator
    latest_status: DeviceStatus | None = None
