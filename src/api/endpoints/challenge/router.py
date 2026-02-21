# -*- coding: utf-8 -*-

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response, Depends, Query, Body
from fastapi.responses import HTMLResponse, RedirectResponse

from api.core.constants import ErrorCodeEnum
from api.core.dependencies.auth import auth_api_key
from api.core.exceptions import BaseHTTPException
from api.core.responses import BaseResponse
from api.core.schemas import BaseResPM
from api.logger import logger

from . import service
from .schemas import FingerprintPayload, Fingerprinter, MinerCollect


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
    logger.debug(f"[{_request_id}] - Redirecting device ID {device_id}...")

    try:
        _url, _device_order = service.get_redirect_url(device_id=device_id)
        logger.debug(f"[{_request_id}] - Redirecting device {device_id} to {_url}")

        # Use FastAPI's RedirectResponse for better handling
        query = urlencode({"order_id": _device_order})
        logger.info(
            f"[{_request_id}] - Redirecting Device {device_id} to {_url}?{query} "
        )
        return RedirectResponse(
            url=f"{_url}?{query}",
            status_code=307,
            headers={
                "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
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
    logger.debug(f"[{_request_id}] - Serving webpage for order ID {order_id}...")
    try:
        _html_response = await service.get_web(request=request, order_id=order_id)
        logger.debug(
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
    logger.debug(
        f"[{_request_id}] - Submitting fingerprint for order ID {payload.order_id}..."
    )
    try:
        await service.submit_fingerprint(payload=payload)
        logger.debug(
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


@router.get(
    "/miner-test",
    summary="Miner Testing Sandbox",
    description="Renders the miner testing sandbox page for device fingerprinting testing.",
    response_class=HTMLResponse,
)
async def get_miner_test(request: Request):
    _request_id = request.state.request_id
    logger.debug(f"[{_request_id}] - Serving miner test page...")
    try:
        _html_response = await service.get_miner_test_page(request=request)
        logger.debug(f"[{_request_id}] - Successfully served miner test page.")
    except Exception:
        logger.exception(f"[{_request_id}] - Failed to serve miner test page!")
        raise BaseHTTPException(
            error_enum=ErrorCodeEnum.INTERNAL_SERVER_ERROR,
            message="Failed to serve miner test page!",
        )
    return _html_response


@router.post(
    "/collect",
    summary="Collect fingerprint",
    description="Collects a fingerprint submission from the miner testing sandbox.",
    response_model=BaseResPM,
)
async def post_collect(
    request: Request,
    payload: MinerCollect,
):
    _request_id = request.state.request_id
    logger.debug(
        f"[{_request_id}] - Collecting fingerprint for device {payload.device_label}..."
    )
    try:
        service.collect_fingerprint(data=payload)
        logger.debug(f"[{_request_id}] - Successfully collected fingerprint.")
    except Exception:
        logger.exception(f"[{_request_id}] - Failed to collect fingerprint!")
        raise BaseHTTPException(
            error_enum=ErrorCodeEnum.INTERNAL_SERVER_ERROR,
            message="Failed to collect fingerprint!",
        )

    _response = BaseResponse(
        request=request,
        message="Successfully collected fingerprint.",
    )
    return _response


@router.post(
    "/clean",
    summary="Clean miner test session",
    description="Clears all collected fingerprints and resets the session.",
    response_model=BaseResPM,
)
async def post_clean(request: Request):
    _request_id = request.state.request_id
    logger.debug(f"[{_request_id}] - Cleaning miner test session...")
    try:
        service.clear_miner_data()
        logger.debug(f"[{_request_id}] - Successfully cleaned session.")
    except Exception:
        logger.exception(f"[{_request_id}] - Failed to clean session!")
        raise BaseHTTPException(
            error_enum=ErrorCodeEnum.INTERNAL_SERVER_ERROR,
            message="Failed to clean session!",
        )

    _response = BaseResponse(
        request=request,
        message="Session cleaned successfully.",
    )
    return _response


@router.get(
    "/results",
    summary="Get miner test results",
    description="Returns scoring results for the current miner test session.",
)
async def get_results(request: Request):
    _request_id = request.state.request_id
    logger.debug(f"[{_request_id}] - Getting miner test results...")
    try:
        _results = service.get_miner_results()
        logger.debug(f"[{_request_id}] - Successfully retrieved results.")
    except Exception:
        logger.exception(f"[{_request_id}] - Failed to get results!")
        raise BaseHTTPException(
            error_enum=ErrorCodeEnum.INTERNAL_SERVER_ERROR,
            message="Failed to get results!",
        )

    return _results


__all__ = [
    "router",
]
