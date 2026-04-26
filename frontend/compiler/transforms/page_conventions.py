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

    bootstrap_ops = _find_op_ids(operations, module="auth", kind_prefix="bootstrap")
    if bootstrap_ops:
        pages.append(
            PageIR(
                id="bootstrap",
                route="/bootstrap",
                file_path="src/app/(auth)/bootstrap/page.tsx",
                title="First-time Setup",
                kind="form",
                entity_slug=None,
                operation_ids=bootstrap_ops,
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
    admin_ops = [op for op in operations if op.module == "admin"]
    if admin_ops:
        pages.append(
            PageIR(
                id="admin-dashboard",
                route="/admin",
                file_path="src/app/(dashboard)/admin/page.tsx",
                title="Admin Dashboard",
                kind="dashboard",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, module="admin"),
                layout="admin",
            )
        )
        admin_kinds = {op.kind for op in admin_ops}

        def _has(prefixes: tuple[str, ...]) -> bool:
            return any(k.startswith(p) for k in admin_kinds for p in prefixes)

        if _has(("listUsers", "getUser", "activateUser", "deactivateUser", "updateUserRole")):
            pages.append(
                PageIR(
                    id="admin-users",
                    route="/admin/users",
                    file_path="src/app/(dashboard)/admin/users/page.tsx",
                    title="Users",
                    kind="list",
                    entity_slug=None,
                    operation_ids=_find_op_ids(operations, module="admin", kind_prefix="listUsers")
                    + _find_op_ids(operations, module="admin", kind_prefix="activateUser")
                    + _find_op_ids(operations, module="admin", kind_prefix="deactivateUser")
                    + _find_op_ids(operations, module="admin", kind_prefix="updateUserRole"),
                    layout="admin",
                )
            )

        if _has(("listApplications", "approveApplication", "rejectApplication")):
            pages.append(
                PageIR(
                    id="admin-applications",
                    route="/admin/applications",
                    file_path="src/app/(dashboard)/admin/applications/page.tsx",
                    title="Applications",
                    kind="list",
                    entity_slug=None,
                    operation_ids=_find_op_ids(operations, module="admin", kind_prefix="listApplications")
                    + _find_op_ids(operations, module="admin", kind_prefix="approveApplication")
                    + _find_op_ids(operations, module="admin", kind_prefix="rejectApplication"),
                    layout="admin",
                )
            )

        if _has(("listFaqs", "createFaq", "updateFaq", "deleteFaq")):
            pages.append(
                PageIR(
                    id="admin-faqs",
                    route="/admin/faqs",
                    file_path="src/app/(dashboard)/admin/faqs/page.tsx",
                    title="FAQs",
                    kind="list",
                    entity_slug=None,
                    operation_ids=_find_op_ids(operations, module="admin", kind_prefix="listFaqs")
                    + _find_op_ids(operations, module="admin", kind_prefix="createFaq")
                    + _find_op_ids(operations, module="admin", kind_prefix="updateFaq")
                    + _find_op_ids(operations, module="admin", kind_prefix="deleteFaq"),
                    layout="admin",
                )
            )

        if _has(("getAiSettings", "updateAiSettings", "getAiProviders", "getAiModels", "listPrompts", "updatePrompt", "listDocuments")):
            pages.append(
                PageIR(
                    id="admin-ai",
                    route="/admin/ai",
                    file_path="src/app/(dashboard)/admin/ai/page.tsx",
                    title="AI Settings",
                    kind="form",
                    entity_slug=None,
                    operation_ids=_find_op_ids(operations, module="admin", kind_prefix="getAiSettings")
                    + _find_op_ids(operations, module="admin", kind_prefix="updateAiSettings")
                    + _find_op_ids(operations, module="admin", kind_prefix="listPrompts")
                    + _find_op_ids(operations, module="admin", kind_prefix="updatePrompt"),
                    layout="admin",
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
            route="/profiles/[type]/[id]",
            file_path="src/app/(dashboard)/profiles/[type]/[id]/page.tsx",
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

    # ── Files manager ─────────────────────────────────────────────
    files_ops = ops_by_module.get("files", [])
    if files_ops:
        pages.append(
            PageIR(
                id="files",
                route="/files",
                file_path="src/app/(dashboard)/files/page.tsx",
                title="Files",
                kind="list",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, module="files"),
                layout="dashboard",
            )
        )

    # ── AI chat (RAG query playground) ───────────────────────────
    ai_ops = ops_by_module.get("ai", [])
    if any(op.kind in {"query", "followUp"} for op in ai_ops):
        pages.append(
            PageIR(
                id="ai-chat",
                route="/ai",
                file_path="src/app/(dashboard)/ai/page.tsx",
                title="AI Assistant",
                kind="form",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, module="ai"),
                layout="dashboard",
            )
        )

    # ── Onboarding wizard (authenticated) ────────────────────────
    if any(e.permissions.requires_onboarding for e in entities):
        pages.append(
            PageIR(
                id="onboarding",
                route="/onboarding",
                file_path="src/app/(dashboard)/onboarding/page.tsx",
                title="Onboarding",
                kind="form",
                entity_slug=None,
                operation_ids=_find_op_ids(operations, kind_prefix="getDraft")
                + _find_op_ids(operations, kind_prefix="updateDraft")
                + _find_op_ids(operations, kind_prefix="submitDraft"),
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
