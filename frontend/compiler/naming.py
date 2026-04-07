"""Deterministic naming convention helpers for the frontend compiler."""

from __future__ import annotations

import re


def slug_to_pascal(slug: str) -> str:
    """Convert a snake/kebab slug to PascalCase.

    >>> slug_to_pascal("producer")
    'Producer'
    >>> slug_to_pascal("primary_crops")
    'PrimaryCrops'
    """
    return "".join(word.capitalize() for word in re.split(r"[-_]", slug))


def slug_to_camel(slug: str) -> str:
    """Convert a snake/kebab slug to camelCase.

    >>> slug_to_camel("get_producer_draft")
    'getProducerDraft'
    """
    parts = re.split(r"[-_]", slug)
    return parts[0].lower() + "".join(w.capitalize() for w in parts[1:])


def slug_to_kebab(slug: str) -> str:
    """Convert a snake_case slug to kebab-case.

    >>> slug_to_kebab("primary_crops")
    'primary-crops'
    """
    return slug.replace("_", "-")


def operation_id(kind: str, entity_slug: str) -> str:
    """Build a deterministic operation ID.

    >>> operation_id("getDraft", "producer")
    'getProducerDraft'
    """
    pascal = slug_to_pascal(entity_slug)
    if kind.startswith("get") or kind.startswith("update") or kind.startswith("submit"):
        prefix_end = next(
            (i for i, c in enumerate(kind) if c.isupper()),
            len(kind),
        )
        prefix = kind[:prefix_end]
        suffix = kind[prefix_end:]
        return f"{prefix}{pascal}{suffix}"
    return f"{kind}{pascal}"


def hook_name(op_id: str) -> str:
    """Derive a React hook name from an operation ID.

    >>> hook_name("getProducerDraft")
    'useProducerDraft'
    >>> hook_name("updateProducerDraft")
    'useUpdateProducerDraft'
    """
    if op_id.startswith("get"):
        body = op_id[3:]
        return f"use{body}"
    return f"use{op_id[0].upper()}{op_id[1:]}"


def cache_key(module: str, entity_slug: str | None, suffix: str) -> str:
    """Build a stable cache key array literal.

    >>> cache_key("profiles", "producer", "draft")
    '["profiles", "producer", "draft"]'
    """
    parts = [f'"{module}"']
    if entity_slug:
        parts.append(f'"{entity_slug}"')
    if suffix:
        parts.append(f'"{suffix}"')
    return f"[{', '.join(parts)}]"


def api_client_filename(module: str) -> str:
    """Filename for a generated API client module.

    >>> api_client_filename("profiles")
    'profiles.ts'
    """
    return f"{slug_to_kebab(module)}.ts"


def hook_filename(module: str) -> str:
    """Filename for a generated hooks module.

    >>> hook_filename("profiles")
    'use-profiles.ts'
    """
    return f"use-{slug_to_kebab(module)}.ts"
