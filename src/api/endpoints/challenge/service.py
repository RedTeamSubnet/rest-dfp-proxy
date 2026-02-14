# -*- coding: utf-8 -*-

import os
import pathlib
import uuid

import aiofiles
import aiohttp
from api.logger import logger
from pydantic import validate_call
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from api.config import config

from .schemas import Fingerprinter, FingerprintPayload, DeviceSession


_API_DIR = str(pathlib.Path(__file__).resolve().parents[2])

# In-memory storage for session mappings
# Key: order_id (int)
_ORDER_SESSIONS: dict[int, DeviceSession] = {}

# Map physical device_id to its current active order_id
_DEVICE_TO_ORDER: dict[int, int] = {}


@validate_call
def set_device_session(device_id: int, order_id: int) -> None:
    _session = DeviceSession(device_id=device_id, order_id=order_id)
    _ORDER_SESSIONS[order_id] = _session
    _DEVICE_TO_ORDER[device_id] = order_id

    logger.debug(f"Mapped Device {device_id} -> Order {order_id}")
    return


@validate_call
def get_redirect_url(device_id: int) -> str:
    _order_id = _DEVICE_TO_ORDER.get(device_id)
    if _order_id is None:
        raise ValueError(f"No active session found for Device {device_id}")

    return f"/_web?order_id={_order_id}"


@validate_call
async def save_fingerprinter(fingerprinter: Fingerprinter, order_id: int) -> None:

    # 1. Generate a random filename to avoid caching
    _random_hex = uuid.uuid4().hex[:8]
    _filename = f"fingerprinter_{_random_hex}.js"

    # 2. Save the file
    _fp_js_path = os.path.join(_API_DIR, "static", "js", _filename)
    async with aiofiles.open(_fp_js_path, "w") as _file:
        await _file.write(fingerprinter.fingerprinter_js)

    # 3. Link filename to session
    if order_id in _ORDER_SESSIONS:
        # FIXED: Use .model_copy() for Pydantic V2
        _ORDER_SESSIONS[order_id] = _ORDER_SESSIONS[order_id].model_copy(
            update={"js_filename": _filename}
        )

    logger.debug(f"Saved fingerprinter JS for Order {order_id} as '{_filename}'")
    return


@validate_call(config={"arbitrary_types_allowed": True})
async def get_web(request: Request, order_id: int) -> HTMLResponse:

    _session = _ORDER_SESSIONS.get(order_id)
    # Fallback to default if session or filename is missing
    _js_name = (
        _session.js_filename
        if _session and _session.js_filename
        else "fingerprinter.js"
    )

    _templates = Jinja2Templates(directory=os.path.join(_API_DIR, "templates", "html"))
    _html_response: HTMLResponse = _templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"fingerprinter_js_path": f"/static/js/{_js_name}"},
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
    return _html_response


@validate_call
def delete_session(order_id: int) -> None:
    _session = _ORDER_SESSIONS.pop(order_id, None)
    if _session:
        _DEVICE_TO_ORDER.pop(_session.device_id, None)

        # 4. Clean up the physical file from disk
        if _session.js_filename:
            _file_path = os.path.join(_API_DIR, "static", "js", _session.js_filename)
            try:
                if os.path.exists(_file_path):
                    os.remove(_file_path)
                    logger.debug(f"Deleted fingerprinter file: {_session.js_filename}")
            except Exception as e:
                logger.error(f"Failed to delete file {_session.js_filename}: {e}")


@validate_call
async def submit_fingerprint(payload: FingerprintPayload) -> None:

    _url = f"{str(config.challenge.base_url).rstrip('/')}/_fingerprint"
    _headers = {
        "X-API-Key": config.challenge.api_key.get_secret_value(),
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as _session:
        # Pass the whole model_dump so device_name is included
        async with _session.post(
            _url, headers=_headers, json=payload.model_dump()
        ) as _res:
            _res.raise_for_status()

    # Clean up mappings and file after successful submission
    delete_session(payload.order_id)
    return


__all__ = [
    "set_device_session",
    "get_redirect_url",
    "delete_session",
]
