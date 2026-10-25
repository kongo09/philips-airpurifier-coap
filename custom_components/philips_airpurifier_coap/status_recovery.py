"""Recover silent AMF870/AC3420 observations without changing power or lights."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from aioairctrl import CoAPClient
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, PhilipsApi

WAKE_DELAY = 2.0
WAKE_SETTLE = 0.4
CONTROL_TIMEOUT = 5.0
SUPPORTED_MODELS = {"AMF870", "AC3420"}
BEEP = PhilipsApi.NEW2_BEEP


def valid_beep(value: Any) -> bool:
    """Only accept known device beep settings, including an already muted device."""
    return type(value) is int and value in (0, 100)


class RecoveryError(Exception):
    """A wake or restore command was rejected."""


class StatusRecoveryClient:
    """Serialize control and recovery while retaining the last confirmed beep value."""

    def __init__(self, client: CoAPClient, store: Store, beep: int | None) -> None:
        self._client = client
        self._store = store
        self._beep = beep if valid_beep(beep) else None
        self._pending_beep: int | None = None
        self._lock = asyncio.Lock()

    @classmethod
    async def async_create(
        cls, hass: HomeAssistant, client: CoAPClient, entry_id: str, status: dict | None
    ) -> StatusRecoveryClient:
        """Load the last confirmed setting before starting an observation."""
        store = Store(hass, 1, f"{DOMAIN}.{entry_id}.recovery")
        saved = await store.async_load()
        beep = saved.get("beep") if isinstance(saved, dict) else None
        if not valid_beep(beep):
            beep = (status or {}).get(BEEP)
        return cls(client, store, beep)

    def with_client(self, client: CoAPClient) -> StatusRecoveryClient:
        """Keep confirmed settings when the coordinator replaces the transport."""
        return type(self)(client, self._store, self._beep)

    def _remember(self, value: Any) -> None:
        if valid_beep(value) and value != self._beep:
            self._beep = value
            # Capture the value so an older transport cannot overwrite a newer one.
            self._store.async_delay_save(lambda: {"beep": value}, 1)

    async def set_control_value(self, key: str, value: Any) -> bool:
        """Use the same lock for ordinary controls and temporary recovery writes."""
        return await self.set_control_values({key: value})

    async def set_control_values(self, data: dict[str, Any], **kwargs: Any) -> bool:
        """Remember user settings only after the device accepts the command."""
        async with self._lock:
            result = await self._client.set_control_values(data, **kwargs)
            if result:
                self._remember(data.get(BEEP))
                if valid_beep(data.get(BEEP)):
                    self._pending_beep = data[BEEP]
            return result

    async def shutdown(self) -> None:
        """Close the underlying CoAP transport after observations are stopped."""
        await self._client.shutdown()

    async def get_status(self) -> tuple[dict[str, Any], int]:
        """Read a complete status, allowing one recovery attempt within the timeout."""
        iterator = self.observe_status()
        try:
            async with asyncio.timeout(15):
                return await anext(iterator), 60
        finally:
            await iterator.aclose()

    async def observe_status(self) -> AsyncIterator[dict[str, Any]]:
        """Wake a silent subscription once, suppressing the temporary mute status."""
        first = asyncio.Event()
        queue = asyncio.Queue()
        waking = False
        restore_pending = False
        resting = None
        wake_error = None

        async def receive() -> None:
            try:
                async for status in self._client.observe_status():
                    first.set()
                    queue.put_nowait(("status", status))
            except Exception as exc:
                queue.put_nowait(("error", exc))
            else:
                queue.put_nowait(("end", None))

        async def write(value: int) -> None:
            result = await asyncio.wait_for(
                self._client.set_control_values({BEEP: value}, retry_count=0), CONTROL_TIMEOUT
            )
            if not result:
                raise RecoveryError

        async def wake() -> None:
            nonlocal waking, restore_pending, resting, wake_error
            try:
                try:
                    await asyncio.wait_for(first.wait(), WAKE_DELAY)
                except TimeoutError:
                    pass
                else:
                    return
                async with self._lock:
                    if first.is_set() or self._beep is None:
                        return
                    resting = self._beep
                    waking = restore_pending = True
                    try:
                        # An off -> off command also wakes these devices. Never turn
                        # on a muted buzzer just to manufacture a setting change.
                        await write(0)
                        await asyncio.sleep(WAKE_SETTLE)
                    finally:
                        try:
                            await write(resting)
                        finally:
                            waking = False
            except Exception as exc:
                wake_error = exc
                queue.put_nowait(("error", exc))

        receiver = asyncio.create_task(receive())
        nudger = asyncio.create_task(wake())
        try:
            while True:
                kind, value = await queue.get()
                if kind == "error":
                    raise value
                if kind == "end":
                    return
                if restore_pending:
                    if value.get(BEEP) != resting:
                        continue
                    await asyncio.shield(nudger)
                    if wake_error:
                        raise wake_error
                    restore_pending = False
                # A restoration notification can be queued when a newer user
                # command wins the lock. Do not publish/save that older value.
                if self._pending_beep is not None:
                    if value.get(BEEP) != self._pending_beep:
                        continue
                    self._pending_beep = None
                self._remember(value.get(BEEP))
                yield value
        finally:
            # Cancellation must not leave the user's buzzer muted. Finish the
            # bounded restore before the coordinator closes this transport.
            if waking:
                await asyncio.shield(nudger)
            else:
                nudger.cancel()
            receiver.cancel()
            await asyncio.gather(receiver, nudger, return_exceptions=True)
            if wake_error:
                raise wake_error
