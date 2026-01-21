# -*- coding: utf-8 -*-

import os
import pathlib

import aiofiles
import aiohttp
from api.logger import logger
from pydantic import validate_call
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from api.core import utils
from api.config import config

from .schemas import Fingerprinter, FingerprintPayload


_API_DIR = str(pathlib.Path(__file__).resolve().parents[2])
SESSION_JS = "fingerprinter_session.js"

# In-memory storage for session mappings
# Format: { device_id (int): order_id (int) }
_DEVICE_SESSIONS = {}


@validate_call
def set_device_session(device_id: int, order_id: int) -> None:
    _DEVICE_SESSIONS[device_id] = order_id
    logger.info(f"Mapped Device {device_id} -> Order {order_id}")
    return


@validate_call
def get_redirect_url(device_id: int) -> str:
    _order_id = _DEVICE_SESSIONS.get(device_id)
    if _order_id is None:
        # For robustness, if no session is found, we could maybe log a warning
        # but raising an error is correct as the phone shouldn't be redirecting
        # without an active session initiated by the Challenger.
        raise ValueError(f"No active session found for Device {device_id}")

    return f"/_web?order_id={_order_id}"


@validate_call
async def save_fingerprinter(fingerprinter: Fingerprinter, order_id: int) -> None:

    _fp_js_path = os.path.join(_API_DIR, "static", "js", SESSION_JS)
    async with aiofiles.open(_fp_js_path, "w") as _file:
        await _file.write(fingerprinter.fingerprinter_js)

    return


@validate_call(config={"arbitrary_types_allowed": True})
async def get_web(request: Request, order_id: int) -> HTMLResponse:

    # Always serve the same session script regardless of order_id
    _templates = Jinja2Templates(
        directory=os.path.join(
            pathlib.Path(__file__).parent.parent.parent.parent, "templates", "html"
        )
    )
    _html_response: HTMLResponse = _templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"fingerprinter_js_path": f"/static/js/{SESSION_JS}"},
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
    return _html_response


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

    return


__all__ = [
    "set_device_session",
    "get_redirect_url",
]
