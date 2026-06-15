"""A controllable fake CoAP client for tests."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock


class FakeClient:
    """Minimal stand-in for ``aioairctrl.CoAPClient``."""

    def __init__(self, status: dict[str, Any], timeout: int = 60) -> None:
        """Initialize the fake client."""
        self.initial_status = dict(status)
        self.timeout = timeout
        self.queue: asyncio.Queue[dict] = asyncio.Queue()
        self.shutdown = AsyncMock()
        self.set_control_value = AsyncMock()
        self.set_control_values = AsyncMock()

    async def get_status(self) -> tuple[dict, int]:
        """Return a copy of the initial status and the reporting interval."""
        return dict(self.initial_status), self.timeout

    async def observe_status(self):
        """Yield every status pushed onto the queue (a live stream)."""
        while True:
            yield await self.queue.get()
