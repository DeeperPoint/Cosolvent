"""Contract validation package for e2e tests.

Provides helpers that treat two artifacts as the source of truth:
1. ``openapi/generated_openapi.json`` — route + schema contract.
2. ``marketplace.yaml`` — business-rule contract (participant types, profile
   schemas, onboarding, communication, discovery, auth toggles).

Any runtime response may be validated against both contracts via
``assert_matches_openapi`` / ``assert_marketplace_rules``.
"""

from __future__ import annotations

from .http import ContractClient
from .openapi_contract import (
    OpenAPIContract,
    assert_matches_openapi,
    load_openapi_contract,
)
from .yaml_contract import (
    MarketplaceContract,
    load_marketplace_contract,
)

__all__ = [
    "ContractClient",
    "OpenAPIContract",
    "assert_matches_openapi",
    "load_openapi_contract",
    "MarketplaceContract",
    "load_marketplace_contract",
]
