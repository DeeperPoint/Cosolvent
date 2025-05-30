from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, Response
import httpx

from core.config import settings
from schemas.gateway_schema import ProxyResponse

router = APIRouter()

@router.api_route(
    "/{service}/{path:path}",
    methods=["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"],
    response_model=ProxyResponse,
    responses={502: {"description": "Bad Gateway"}}
)
async def proxy(service: str, path: str, request: Request):
    """
    Proxy any incoming request /{service}/{path} to the corresponding backend URL.
    """
    # empty sub-path 
    if not path:
        raise HTTPException(status_code=404, detail="Path not specified")

    base_url = settings.get_service_url(service)
    if not base_url:
        raise HTTPException(status_code=404, detail="Service not found")

    target_url = f"{base_url.rstrip('/')}/{path}"

    try:
        async with httpx.AsyncClient() as client:
            forwarded = client.build_request(
                method=request.method,
                url=target_url,
                headers=request.headers.raw,
                content=await request.body(),
                params=request.query_params,
            )
            resp = await client.send(forwarded, stream=False)
    except httpx.RequestError as exc:
        # upstream is unreachable, bubble as 502
        raise HTTPException(status_code=502, detail=f"Bad gateway: {exc}") from exc

    content_type = resp.headers.get("content-type", "")
    # If response is JSON, use envelope JSONResponse
    if "application/json" in content_type:
        body = resp.json()
        return JSONResponse(
            status_code=resp.status_code,
            content={"status_code": resp.status_code, "content": body},
            headers={"x-upstream-content-type": content_type},
        )
    # For non-JSON, return raw response with correct Content-Type
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={"content-type": content_type},
        media_type=content_type,
    )
