"""Derive sidebar navigation from entities and pages."""

from __future__ import annotations

from ..ir import EntityIR, NavItemIR, NavigationIR, PageIR


def derive_navigation(
    entities: tuple[EntityIR, ...],
    pages: tuple[PageIR, ...],
) -> NavigationIR:
    all_slugs = tuple(e.slug for e in entities)
    page_ids = {p.id for p in pages}
    items: list[NavItemIR] = []

    items.append(
        NavItemIR(
            label="Dashboard",
            route="/",
            icon="LayoutDashboard",
            roles=all_slugs,
        )
    )

    if "search" in page_ids:
        searcher_slugs = tuple(e.slug for e in entities if e.permissions.can_search)
        items.append(
            NavItemIR(
                label="Search",
                route="/search",
                icon="Search",
                roles=searcher_slugs if searcher_slugs else all_slugs,
            )
        )

    items.append(
        NavItemIR(
            label="My Profile",
            route="/profile",
            icon="User",
            roles=all_slugs,
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
                roles=conv_slugs if conv_slugs else all_slugs,
            )
        )

    if "notifications" in page_ids:
        items.append(
            NavItemIR(
                label="Notifications",
                route="/notifications",
                icon="Bell",
                roles=all_slugs,
            )
        )

    return NavigationIR(items=tuple(items))
