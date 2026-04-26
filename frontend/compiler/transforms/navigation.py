"""Derive sidebar navigation from entities and pages."""

from __future__ import annotations

from ..ir import DiscoveryIR, EntityIR, NavItemIR, NavigationIR, OperationIR, PageIR


def derive_navigation(
    entities: tuple[EntityIR, ...],
    operations: tuple[OperationIR, ...],
    pages: tuple[PageIR, ...],
    discovery: DiscoveryIR | None = None,
) -> NavigationIR:
    base_roles = tuple(e.slug for e in entities)
    all_roles = tuple(dict.fromkeys((*base_roles, "admin")))
    page_ids = {p.id for p in pages}
    items: list[NavItemIR] = []

    # Dashboard is only meaningful for participants (supply/demand). Admins
    # have their own dashboard at /admin and clicking "Dashboard" would just
    # bounce them via the role-router — confusing UX. Hide it for admins.
    items.append(
        NavItemIR(
            label="Dashboard",
            route="/dashboard",
            icon="LayoutDashboard",
            roles=base_roles,
        )
    )

    # Admins don't onboard or hold a participant profile, so they don't see
    # "My Profile". They get the lightweight "Account" page (email + change
    # password) appended further down.
    items.append(
        NavItemIR(
            label="My Profile",
            route="/profile",
            icon="User",
            roles=base_roles,
        )
    )
    items.append(
        NavItemIR(
            label="Account",
            route="/account",
            icon="Settings",
            roles=("admin",),
        )
    )

    if "conversations" in page_ids:
        conv_slugs = tuple(
            e.slug
            for e in entities
            if e.permissions.can_initiate_conversation
            or e.permissions.can_receive_conversation
        )
        items.append(
            NavItemIR(
                label="Messages",
                route="/conversations",
                icon="MessageSquare",
                roles=conv_slugs if conv_slugs else base_roles,
            )
        )

    if "notifications" in page_ids:
        items.append(
            NavItemIR(
                label="Notifications",
                route="/notifications",
                icon="Bell",
                roles=all_roles,
            )
        )

    # Search sits next to Notifications (per UX request). Label is derived
    # from ``discovery.searchable_types`` so a marketplace declaring
    # ``searchable_types: ["producer"]`` shows "Search Producers" — driven
    # entirely by marketplace.yaml, not hand-typed.
    if "search" in page_ids:
        searcher_slugs = tuple(e.slug for e in entities if e.permissions.can_search)
        search_label = _search_nav_label(entities, discovery)
        items.append(
            NavItemIR(
                label=search_label,
                route="/search",
                icon="Search",
                roles=searcher_slugs if searcher_slugs else base_roles,
            )
        )

    if "files" in page_ids:
        items.append(
            NavItemIR(
                label="Files",
                route="/files",
                icon="FolderOpen",
                roles=all_roles,
            )
        )

    if "ai-chat" in page_ids:
        items.append(
            NavItemIR(
                label="AI Assistant",
                route="/ai",
                icon="Sparkles",
                roles=all_roles,
            )
        )

    if any(op.module == "admin" for op in operations):
        items.append(
            NavItemIR(
                label="Admin",
                route="/admin",
                icon="Shield",
                roles=("admin",),
            )
        )

    # API explorer is an operator/diagnostic tool, not user-facing chrome.
    # Hide it for participant roles (supply/demand) — admins keep it in the sidebar.
    items.append(
        NavItemIR(
            label="API explorer",
            route="/dev/api-explorer",
            icon="Terminal",
            roles=("admin",),
        )
    )

    return NavigationIR(items=tuple(items))


def _search_nav_label(
    entities: tuple[EntityIR, ...],
    discovery: DiscoveryIR | None,
) -> str:
    """Derive the Search nav label from the discoverable participant types.

    >>> _search_nav_label((EntityIR(slug="producer", name="Producer", ...),),
    ...                  DiscoveryIR(searchable_types=("producer",), ...))
    'Search Producers'
    """
    if discovery is None or not discovery.searchable_types:
        return "Search"
    name_by_slug = {e.slug: e.name for e in entities}
    plural_names = [
        _pluralize(name_by_slug.get(slug, slug.replace("_", " ").title()))
        for slug in discovery.searchable_types
    ]
    if not plural_names:
        return "Search"
    return "Search " + " & ".join(plural_names)


def _pluralize(name: str) -> str:
    """Naive English pluraliser. Good enough for participant-type labels."""
    if not name:
        return name
    lower = name.lower()
    if lower.endswith("s"):
        return name
    if lower.endswith("y") and not lower.endswith(("ay", "ey", "iy", "oy", "uy")):
        return name[:-1] + "ies"
    if lower.endswith(("ch", "sh", "x", "z")):
        return name + "es"
    return name + "s"
