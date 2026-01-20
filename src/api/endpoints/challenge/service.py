# -*- coding: utf-8 -*-

import os
import pathlib

import aiofiles
import aiohttp
from pydantic import validate_call
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from api.core import utils
from api.config import config

from .schemas import Fingerprinter, FingerprintPayload


_API_DIR = str(pathlib.Path(__file__).resolve().parents[2])
SESSION_JS = "fingerprinter_session.js"


@validate_call
async def save_fingerprinter(fingerprinter: Fingerprinter, order_id: int) -> None:

    _fp_js_path = os.path.join(_API_DIR, "static", "js", SESSION_JS)
    async with aiofiles.open(_fp_js_path, "w") as _file:
        await _file.write(fingerprinter.fingerprinter_js)

    return


@validate_call(config={"arbitrary_types_allowed": True})
async def get_web(request: Request, order_id: int) -> HTMLResponse:

    # Always serve the same session script regardless of order_id
    _templates = Jinja2Templates(directory=os.path.join(_API_DIR, "templates", "html"))
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
        async with _session.post(_url, headers=_headers, json=payload.model_dump()) as _res:
            _res.raise_for_status()

    return


__all__ = [
    "save_fingerprinter",
    "get_web",
    "submit_fingerprint",
]