"""Derive sidebar navigation from entities and pages."""

from __future__ import annotations

from ..ir import EntityIR, NavItemIR, NavigationIR, OperationIR, PageIR


def derive_navigation(
    entities: tuple[EntityIR, ...],
    operations: tuple[OperationIR, ...],
    pages: tuple[PageIR, ...],
) -> NavigationIR:
    base_roles = tuple(e.slug for e in entities)
    all_roles = tuple(dict.fromkeys((*base_roles, "admin")))
    page_ids = {p.id for p in pages}
    items: list[NavItemIR] = []

    items.append(
        NavItemIR(
            label="Dashboard",
            route="/dashboard",
            icon="LayoutDashboard",
            roles=all_roles,
        )
    )

    if "search" in page_ids:
        searcher_slugs = tuple(e.slug for e in entities if e.permissions.can_search)
        items.append(
            NavItemIR(
                label="Search",
                route="/search",
                icon="Search",
                roles=searcher_slugs if searcher_slugs else base_roles,
            )
        )

    items.append(
        NavItemIR(
            label="My Profile",
            route="/profile",
            icon="User",
            roles=all_roles,
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

    if any(op.module == "admin" for op in operations):
        items.append(
            NavItemIR(
                label="Admin",
                route="/admin",
                icon="Shield",
                roles=("admin",),
            )
        )

    items.append(
        NavItemIR(
            label="API explorer",
            route="/dev/api-explorer",
            icon="Terminal",
            roles=all_roles,
        )
    )

    return NavigationIR(items=tuple(items))
