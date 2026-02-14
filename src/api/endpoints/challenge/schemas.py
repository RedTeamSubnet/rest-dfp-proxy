# -*- coding: utf-8 -*-
import os
import pathlib

from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from api.logger import logger


_app_dir = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
_dfp_template_dir = _app_dir / "static" / "js"

_dfp_js_path = str(_dfp_template_dir / "fingerprinter.js")
_dfp_js_content = ""

try:
    if os.path.exists(_dfp_js_path):
        with open(_dfp_js_path, "r") as _dfp_js_file:
            _dfp_js_content = _dfp_js_file.read()
except Exception:
    logger.exception(f"Failed to read fingerprinter.js file!")


class Fingerprinter(BaseModel):
    fingerprinter_js: str = Field(
        title="fingerprinter.js",
        min_length=2,
        description="System-provided fingerprinter.js script for fingerprint detection.",
        examples=[_dfp_js_content],
    )

    @field_validator("fingerprinter_js", mode="after")
    @classmethod
    def _check_fingerprinter_js_lines(cls, val: str) -> str:
        _lines = val.split("\n")
        if len(_lines) > 1000:
            raise ValueError(
                "fingerprinter_js content is too long, max 1000 lines are allowed!"
            )
        return val


class FingerprintPayload(BaseModel):
    order_id: int = Field(..., ge=0, lt=1000000)
    fingerprint: str = Field(
        ..., min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9+/=-]+$"
    )


class DeviceSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    device_id: int = Field(..., ge=0)
    order_id: int = Field(..., ge=0, lt=1000000)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: Literal["active", "completed", "expired"] = "active"

    device_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    js_filename: Optional[str] = Field(default=None, min_length=1, max_length=128)


__all__ = ["Fingerprinter", "FingerprintPayload", "DeviceSession"]
