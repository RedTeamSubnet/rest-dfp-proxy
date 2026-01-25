# -*- coding: utf-8 -*-

from fastapi import APIRouter, HTTPException, Request, Response, Depends, Query, Body
from fastapi.responses import HTMLResponse

from api.core.constants import ErrorCodeEnum
from api.core.dependencies.auth import auth_api_key
from api.core.exceptions import BaseHTTPException
from api.core.responses import BaseResponse
from api.core.schemas import BaseResPM
from api.logger import logger

from . import service
from .schemas import FingerprintPayload, Fingerprinter


router = APIRouter(tags=["Challenge"])


@router.post("/_fp-js", dependencies=[Depends(auth_api_key)])
async def post_fp_js(
    fingerprinter: Fingerprinter, order_id: int = Query(..., ge=0, lt=1000000)
):
    await service.save_fingerprinter(fingerprinter=fingerprinter, order_id=order_id)
    return BaseResponse(message="Successfully saved miner fingerprinter.")


@router.post("/set_device_session", dependencies=[Depends(auth_api_key)])
def set_device_session(
    device_id: int = Body(..., ge=0), order_id: int = Body(..., ge=0)
):
    service.set_device_session(device_id=device_id, order_id=order_id)
    return BaseResponse(message="Device session set successfully.")


@router.get(
    "/redirect",
    summary="Redirect device to dynamic challenge URL",
    description="This endpoint redirects a device to its dynamic session URL on the proxy.",
    response_class=Response,
)
def get_redirect(request: Request, device_id: int = Query(..., ge=0)):
    _request_id = request.state.request_id
    logger.info(f"[{_request_id}] - Redirecting device ID {device_id}...")

    try:
        _url = service.get_redirect_url(device_id=device_id)
        logger.success(f"[{_request_id}] - Redirecting device {device_id} to {_url}")

        # Return a 307 Redirect with "no-referrer" policy
        # This prevents the destination page (Miner JS) from seeing "device_id=X" in document.referrer
        return Response(
            status_code=307,
            headers={"Location": _url, "Referrer-Policy": "no-referrer"},
        )
    except Exception as e:
        logger.warning(f"[{_request_id}] - Failed to redirect device {device_id}: {e}")
        # Fallback or error page could go here, but raising 404 is standard if session not active
        raise HTTPException(
            status_code=404, detail="Session not active or device not found"
        )


@router.get(
    "/_web",
    summary="Serves the webpage",
    description="This endpoint serves the webpage for the challenge.",
    responses={422: {}},
    response_class=HTMLResponse,
)
async def get_web(request: Request, order_id: int = Query(..., ge=0, lt=1000000)):

    _request_id = request.state.request_id
    logger.info(f"[{_request_id}] - Serving webpage for order ID {order_id}...")
    try:
        _html_response = await service.get_web(request=request, order_id=order_id)
        logger.success(
            f"[{_request_id}] - Successfully served webpage for order ID {order_id}."
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            f"[{_request_id}] - Failed to serve webpage for order ID {order_id}!"
        )
        raise BaseHTTPException(
            error_enum=ErrorCodeEnum.INTERNAL_SERVER_ERROR,
            message="Failed to serve webpage!",
        )

    return _html_response


@router.post(
    "/fingerprint",
    summary="Submit the fingerprint",
    description="This endpoint receives the fingerprint data and submit it to challenger service.",
    response_model=BaseResPM,
    responses={422: {}},
)
async def post_fingerprint(
    request: Request,
    payload: FingerprintPayload,
):

    _request_id = request.state.request_id
    logger.info(
        f"[{_request_id}] - Submitting fingerprint for order ID {payload.order_id}..."
    )
    try:
        await service.submit_fingerprint(payload=payload)
        logger.success(
            f"[{_request_id}] - Successfully submitted fingerprint for order ID {payload.order_id}."
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            f"[{_request_id}] - Failed to submit fingerprint for order ID {payload.order_id}!"
        )
        raise BaseHTTPException(
            error_enum=ErrorCodeEnum.INTERNAL_SERVER_ERROR,
            message="Failed to submit fingerprint!",
        )

    _response = BaseResponse(
        request=request,
        message="Successfully submitted fingerprint.",
    )
    return _response


__all__ = [
    "router",
]
