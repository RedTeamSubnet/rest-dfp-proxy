# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field, field_validator

_fingerprinter_js_content = """(function(){const e=new URLSearchParams(window.location.search).get("order_id"),n={userAgent:navigator.userAgent},t={fingerprint:btoa(JSON.stringify(n)).slice(0,32),timestamp:(new Date).toISOString(),order_id:e,device_name:navigator.platform};fetch(window.ENDPOINT,{method:"POST",body:JSON.stringify(t),headers:{"Content-Type":"application/json","Accept":"application/json"}}).then(e=>e.ok?e.json():Promise.reject(new Error(`HTTP error! status: ${e.status}`))).catch(e=>console.error("Error sending fingerprint:",e));})();"""


class Fingerprinter(BaseModel):
    fingerprinter_js: str = Field(
        title="fingerprinter.js",
        min_length=2,
        description="System-provided fingerprinter.js script for fingerprint detection.",
        examples=[_fingerprinter_js_content],
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
        ..., min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9-]+$"
    )
    device_name: str | None = Field(default=None, min_length=1, max_length=128)


__all__ = ["Fingerprinter", "FingerprintPayload"]
