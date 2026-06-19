"""Helper functions for Philips air purifier status."""

import asyncio
import logging

from .const import PhilipsApi

_LOGGER = logging.getLogger(__name__)


async def get_status_with_trigger(client) -> tuple[dict, int]:
    """Get device status, with a control trigger fallback for push-only devices.

    Some devices (e.g. CX3550) silently ignore the initial CoAP observe GET
    and never send the first status push, causing setup to time out.  They do,
    however, push a status update after receiving any encrypted control command.
    We try the normal path first; on timeout we register the observe, fire a
    beep-off command (D03130=0) to prompt the push, then collect the result.

    See: https://github.com/kongo09/philips-airpurifier-coap/issues/205
    """
    try:
        return await asyncio.wait_for(client.get_status(), timeout=10)
    except (asyncio.TimeoutError, TimeoutError):
        pass

    _LOGGER.debug("get_status timed out, trying control-trigger approach")

    status_holder: dict = {}

    async def _collect() -> None:
        async for status in client.observe_status():
            status_holder["status"] = status
            return

    collect_task = asyncio.create_task(_collect())
    # Yield so the observe GET is dispatched before the trigger is sent.
    await asyncio.sleep(0.5)
    try:
        await asyncio.wait_for(client.set_control_values({"D03130": 0}), timeout=10)
    except Exception:
        collect_task.cancel()
        raise

    await asyncio.wait_for(collect_task, timeout=20)

    if "status" not in status_holder:
        raise TimeoutError("Device did not push status after control trigger")

    return status_holder["status"], 60


def extract_name(status: dict) -> str:
    """Extract the name from the status."""
    for name_key in [PhilipsApi.NAME, PhilipsApi.NEW_NAME, PhilipsApi.NEW2_NAME]:
        name = status.get(name_key)
        if name:
            return name
    return ""


def extract_model(status: dict) -> str:
    """Extract the model from the status."""
    for model_key in [
        PhilipsApi.MODEL_ID,
        PhilipsApi.NEW_MODEL_ID,
        PhilipsApi.NEW2_MODEL_ID,
    ]:
        model = status.get(model_key)
        if model:
            return model[:9]
    return ""
