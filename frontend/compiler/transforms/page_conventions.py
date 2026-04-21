"""Derive pages from entities, operations, and config using conventions.

Each entity's permissions determine which pages are generated.
Auth config drives login/signup pages.
"""

from __future__ import annotations

from ..ir import (
    AuthIR,
    DiscoveryIR,
    EntityIR,
    OperationIR,
    PageIR,
)


def derive_pages(
    entities: tuple[EntityIR, ...],
    operations: tuple[OperationIR, ...],
    auth: AuthIR,
    discovery: DiscoveryIR,
) -> tuple[PageIR, ...]:
    pages: list[PageIR] = []
    ops_by_module: dict[str, list[OperationIR]] = {}
    for op in operations:
        ops_by_module.setdefault(op.module, []).append(op)

    # ── Auth pages ────────────────────────────────────────────────
    pages.append(
        PageIR(
            id="login",
            route="/login",
            file_path="src/app/(auth)/login/page.tsx",
            title="Sign In",
            kind="form",
            entity_slug=None,
            operation_ids=_find_op_ids(operations, module="auth", kind_prefix="login"),
            layout="auth",
        )
    )

    if auth.allow_public_signup:
        pages.append(
            PageIR(
                id="signup",
                route="/signup",
                file_path="src/app/(auth)/signup/page.tsx",
                title="Create Account",
                kind="form",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, module="auth", kind_prefix="signup"),
                layout="auth",
            )
        )

    # ── Dashboard ─────────────────────────────────────────────────
    pages.append(
        PageIR(
            id="dashboard",
            route="/dashboard",
            file_path="src/app/(dashboard)/dashboard/page.tsx",
            title="Dashboard",
            kind="dashboard",
            entity_slug=None,
            operation_ids=(),
            layout="dashboard",
        )
    )
    if any(op.module == "admin" for op in operations):
        pages.append(
            PageIR(
                id="admin-dashboard",
                route="/admin",
                file_path="src/app/(dashboard)/admin/page.tsx",
                title="Admin Dashboard",
                kind="dashboard",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, module="admin"),
                layout="dashboard",
            )
        )

    # ── Profile pages ─────────────────────────────────────────────
    pages.append(
        PageIR(
            id="profile-view",
            route="/profile",
            file_path="src/app/(dashboard)/profile/page.tsx",
            title="My Profile",
            kind="detail",
            entity_slug=None,
            operation_ids=_find_op_ids(operations, kind_prefix="getMe"),
            layout="dashboard",
        )
    )
    pages.append(
        PageIR(
            id="profile-edit",
            route="/profile/edit",
            file_path="src/app/(dashboard)/profile/edit/page.tsx",
            title="Edit Profile",
            kind="form",
            entity_slug=None,
            operation_ids=(
                _find_op_ids(operations, kind_prefix="getDraft")
                + _find_op_ids(operations, kind_prefix="updateDraft")
            ),
            layout="dashboard",
        )
    )
    pages.append(
        PageIR(
            id="profile-detail",
            route="/profiles/[id]",
            file_path="src/app/(dashboard)/profiles/[id]/page.tsx",
            title="Profile",
            kind="detail",
            entity_slug=None,
            operation_ids=_find_op_ids(operations, kind_prefix="getProfile"),
            layout="dashboard",
        )
    )

    # ── Search / Discovery ────────────────────────────────────────
    if discovery.searchable_types:
        search_ops = _find_op_ids(operations, module="discovery")
        pages.append(
            PageIR(
                id="search",
                route="/search",
                file_path="src/app/(dashboard)/search/page.tsx",
                title="Search",
                kind="search",
                entity_slug=None,
                operation_ids=tuple(search_ops),
                layout="dashboard",
            )
        )

    # ── Conversations ─────────────────────────────────────────────
    comm_ops = ops_by_module.get("communication", [])
    if comm_ops:
        pages.append(
            PageIR(
                id="conversations",
                route="/conversations",
                file_path="src/app/(dashboard)/conversations/page.tsx",
                title="Messages",
                kind="conversation",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, module="communication"),
                layout="dashboard",
            )
        )
        pages.append(
            PageIR(
                id="conversation-detail",
                route="/conversations/[id]",
                file_path="src/app/(dashboard)/conversations/[id]/page.tsx",
                title="Conversation",
                kind="conversation",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, module="communication"),
                layout="dashboard",
            )
        )

    # ── Notifications ─────────────────────────────────────────────
    notif_ops = ops_by_module.get("notifications", [])
    if notif_ops:
        pages.append(
            PageIR(
                id="notifications",
                route="/notifications",
                file_path="src/app/(dashboard)/notifications/page.tsx",
                title="Notifications",
                kind="list",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, module="notifications"),
                layout="dashboard",
            )
        )

    # ── Registration (public application) ─────────────────────────
    if auth.allow_public_application:
        pages.append(
            PageIR(
                id="register",
                route="/register/[type]",
                file_path="src/app/register/[type]/page.tsx",
                title="Register",
                kind="form",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, kind_prefix="register"),
                layout="public",
            )
        )

    return tuple(sorted(pages, key=lambda p: p.id))


def _find_op_ids(
    operations: tuple[OperationIR, ...],
    *,
    module: str | None = None,
    kind_prefix: str | None = None,
) -> tuple[str, ...]:
    result: list[str] = []
    for op in operations:
        if module and op.module != module:
            continue
        if kind_prefix and not op.kind.startswith(kind_prefix):
            continue
        result.append(op.id)
    return tuple(sorted(result))
