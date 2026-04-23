"""Contract-aware HTTP helper used across e2e tests.

Wraps ``httpx.AsyncClient`` so a single call both executes the request
and validates the response against ``OpenAPIContract``.  Path templates
are inferred from the request path; callers can pass ``path_template``
explicitly when they want strict matching.
"""

from __future__ import annotations

from typing import Any, Iterable

import httpx

from .openapi_contract import OpenAPIContract, assert_matches_openapi


class ContractClient:
    """Thin wrapper that runs every response through OpenAPI validation."""

    def __init__(self, client: httpx.AsyncClient, contract: OpenAPIContract) -> None:
        self._client = client
        self._contract = contract

    @property
    def raw(self) -> httpx.AsyncClient:
        return self._client

    async def request(
        self,
        method: str,
        path: str,
        *,
        path_template: str | None = None,
        expected_status: int | Iterable[int] | None = None,
        validate: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        response = await self._client.request(method, path, **kwargs)
        if validate:
            assert_matches_openapi(
                response,
                contract=self._contract,
                path_template=path_template,
                method=method,
                expected_status=expected_status,
            )
        return response

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", path, **kwargs)
