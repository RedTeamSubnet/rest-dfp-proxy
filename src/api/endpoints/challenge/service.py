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
from typing import Tuple

from api.config import config

from .schemas import Fingerprinter, FingerprintPayload, DeviceSession, MinerCollect


_API_DIR = str(pathlib.Path(__file__).resolve().parents[2])

# In-memory storage for session mappings
# Key: order_id (int)
_ORDER_SESSIONS: dict[int, DeviceSession] = {}

# Map physical device_id to its current active order_id
_DEVICE_TO_ORDER: dict[int, int] = {}

# In-memory storage for miner testing (single session)
# Value: list of {device_label, fingerprint_hash}
_MINER_DATA: list[dict] = []


@validate_call
def set_device_session(device_id: int, order_id: int) -> None:
    global _ORDER_SESSIONS, _DEVICE_TO_ORDER
    _session = DeviceSession(device_id=device_id, order_id=order_id)
    _ORDER_SESSIONS[order_id] = _session
    _DEVICE_TO_ORDER[device_id] = order_id

    logger.debug(f"Mapped Device {device_id} -> Order {order_id}")
    return


@validate_call
def get_redirect_url(device_id: int) -> Tuple[str, int]:
    global _DEVICE_TO_ORDER
    _order_id = _DEVICE_TO_ORDER.get(device_id)
    if _order_id is None:
        raise ValueError(f"No active session found for Device {device_id}")

    return f"/_web", _order_id


@validate_call
async def save_fingerprinter(fingerprinter: Fingerprinter, order_id: int) -> None:
    global _ORDER_SESSIONS
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
    global _ORDER_SESSIONS
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
            "Referrer-Policy": "no-referrer",
            "Clear-Site-Data": '"cache", "cookies", "storage"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )
    return _html_response


@validate_call
def delete_session(order_id: int) -> None:
    global _ORDER_SESSIONS, _DEVICE_TO_ORDER
    _session = _ORDER_SESSIONS.pop(order_id, None)
    if _session:
        _DEVICE_TO_ORDER.pop(_session.device_id, None)

        # 4. Clean up the physical file from disk
        if _session.js_filename:
            _file_path = os.path.join(_API_DIR, "static", "js", _session.js_filename)
            try:
                if os.path.exists(_file_path):
                    os.remove(_file_path)
                    logger.info(f"Deleted fingerprinter file: {_session.js_filename}")
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


def collect_fingerprint(data: MinerCollect) -> None:
    """Store fingerprint submission in memory (single session)."""
    global _MINER_DATA
    _MINER_DATA.append({
        "device_label": data.device_label,
        "fingerprint_hash": data.fingerprint_hash
    })
    logger.debug(f"Collected fingerprint for device {data.device_label}")


def clear_miner_data() -> None:
    """Clear all stored fingerprints for a fresh session."""
    global _MINER_DATA
    _MINER_DATA.clear()
    logger.info("Miner test data cleared")


def get_miner_results() -> dict:
    """Calculate scoring results using production Two-Strike logic."""
    global _MINER_DATA
    
    if not _MINER_DATA:
        return {
            "devices": [],
            "score": 0.0,
            "breakdown": {"correct": 0, "collisions": 0, "fragmentations": 0}
        }
    
    # Group payloads by device_label
    # { device_label: [payload1, payload2, ...] }
    payloads_by_device: dict[str, list[dict]] = {}
    for p in _MINER_DATA:
        label = p["device_label"]
        if label not in payloads_by_device:
            payloads_by_device[label] = []
        payloads_by_device[label].append(p)
    
    # Build fingerprint -> set of device_labels map
    # { "FP_HASH": {device_1, device_2} }
    devices_sharing_fingerprint: dict[str, set] = {}
    for label, payloads in payloads_by_device.items():
        for p in payloads:
            fp = p["fingerprint_hash"]
            if fp not in devices_sharing_fingerprint:
                devices_sharing_fingerprint[fp] = set()
            devices_sharing_fingerprint[fp].add(label)
    
    # Scoring configuration
    max_fragmentation = 3  # If >= 3 unique hashes, score = 0
    fragmentation_penalty = 0.3
    collision_penalty = 0.25
    
    # Calculate points per device
    total_session_points = 0.0
    target_device_labels = set(payloads_by_device.keys())
    
    correct = 0
    fragmentations = 0
    collisions = 0
    
    for device_label in target_device_labels:
        device_payloads = payloads_by_device.get(device_label, [])
        
        if not device_payloads:
            continue
        
        device_points = 1.0
        unique_fps = {p["fingerprint_hash"] for p in device_payloads}
        unique_fps_count = len(unique_fps)
        
        # Rule 1: Fragmentation (Internal Consistency)
        if unique_fps_count >= max_fragmentation:
            logger.warning(f"Scoring: Device {device_label} reached fragmentation limit ({unique_fps_count} unique IDs).")
            device_points = 0.0
            fragmentations += 1
        elif unique_fps_count > 1:
            penalty = fragmentation_penalty * (unique_fps_count - 1)
            device_points -= penalty
            logger.info(f"Scoring: Device {device_label} fragmented. Penalty: -{penalty:.2f}")
            fragmentations += 1
        else:
            correct += 1
        
        # Rule 2: Two-Strike Collision (External Uniqueness)
        if device_points > 0:
            collision_count = 0
            for p in device_payloads:
                fp = p["fingerprint_hash"]
                # Does this fingerprint match ANY other device?
                if len(devices_sharing_fingerprint[fp]) > 1:
                    collision_count += 1
            
            # Strike 1: 1 collision (-0.25)
            # Strike 2: 2+ collisions (0.0)
            if collision_count >= 2:
                logger.warning(f"Scoring: Device {device_label} failed uniqueness in {collision_count} submissions. Score: 0.0")
                device_points = 0.0
                collisions += 1
            elif collision_count == 1:
                device_points -= collision_penalty
                logger.info(f"Scoring: Device {device_label} collided in 1 submission. Penalty: -{collision_penalty:.2f}")
                collisions += 1
        
        total_session_points += max(0.0, device_points)
    
    # Final normalization (average across all devices)
    final_score = total_session_points / len(target_device_labels) if target_device_labels else 0.0
    
    return {
        "devices": _MINER_DATA,
        "score": round(min(1.0, max(0.0, final_score)), 3),
        "breakdown": {
            "correct": correct,
            "collisions": collisions,
            "fragmentations": fragmentations
        }
    }


@validate_call(config={"arbitrary_types_allowed": True})
async def get_miner_test_page(request: Request) -> HTMLResponse:
    """Render the miner testing sandbox page."""
    _templates = Jinja2Templates(directory=os.path.join(_API_DIR, "templates", "html"))
    _html_response: HTMLResponse = _templates.TemplateResponse(
        request=request,
        name="miner_test.html",
        context={},
        headers={
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
    return _html_response


__all__ = [
    "set_device_session",
    "get_redirect_url",
    "delete_session",
    "collect_fingerprint",
    "get_miner_results",
    "get_miner_test_page",
]
