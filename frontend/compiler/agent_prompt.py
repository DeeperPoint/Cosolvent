"""Prompt builder for constrained AGENT_FILL second pass.

Two messages are sent to the model:

* ``build_system_prompt(ir)`` — a constant-per-run "design contract" that
  fixes the UI vocabulary (shadcn/ui inventory, spacing, states, voice).
* ``build_fill_prompt(...)`` — a per-file user message that gives marker
  IDs, page-specific IR facts (entity / fields / page intent), and the
  raw file body.
"""

from __future__ import annotations

import hashlib
import json
import re

from .ir import EntityIR, FrontendIR, OperationIR


# ── UI component & hook inventory (scaffolded by the deterministic pass) ──

_UI_INVENTORY = """\
Components — IMPORT and PREFER over raw HTML:
  @/components/ui/button       — <Button variant="default|outline|ghost|destructive|link" size="sm|md|lg">
  @/components/ui/card         — <Card><CardHeader><CardTitle/><CardDescription/></CardHeader><CardContent/></Card>
  @/components/ui/input        — <Input id type value onChange placeholder disabled/>
  @/components/ui/label        — <Label htmlFor>...</Label>
  @/components/ui/select       — <Select value onValueChange><SelectTrigger><SelectValue/></SelectTrigger><SelectContent><SelectItem value/></SelectContent></Select>
  @/components/ui/tabs         — <Tabs defaultValue><TabsList><TabsTrigger value/></TabsList><TabsContent value/></Tabs>
  @/components/ui/dialog       — <Dialog open onOpenChange><DialogTrigger asChild/><DialogContent><DialogHeader><DialogTitle/></DialogHeader></DialogContent></Dialog>
  @/components/ui/dropdown-menu — <DropdownMenu><DropdownMenuTrigger asChild/><DropdownMenuContent><DropdownMenuItem/></DropdownMenuContent></DropdownMenu>
  @/components/ui/avatar       — <Avatar><AvatarImage src/><AvatarFallback>XX</AvatarFallback></Avatar>
  @/components/ui/badge        — <Badge variant="default|secondary|outline|destructive">...</Badge>
  @/components/ui/separator    — <Separator orientation="horizontal|vertical"/>
  @/components/ui/skeleton     — <Skeleton className="h-4 w-32"/>  (use in loading states; mirror final layout)
  @/components/ui/table        — <Table><TableHeader><TableRow><TableHead/></TableRow></TableHeader><TableBody><TableRow><TableCell/></TableRow></TableBody></Table>
  @/components/ui/tabs         — see above
  @/components/ui/toast        — useToast() hook: const { toast } = useToast(); toast({title, description, variant: "destructive"})

Shared:
  @/components/shared/profile-card     — <ProfileCard profile={...}/>  (cards in lists/grids)
  @/components/shared/search-filters   — <SearchFilters .../>           (search page chrome)
  @/components/forms/field-renderer    — renders one IR field by name + value; use inside forms

Icons: import from "lucide-react" only. Common: ArrowRight, Check, ChevronDown, Plus, Pencil, Trash2, Search, Bell, MessageSquare, FolderOpen, User, Shield, Sparkles, AlertCircle, CheckCircle2, Loader2.

Generated hooks already wired in pages — do NOT redefine, just use:
  useAuth(), useCurrentProfile<T>()  → from @/generated/hooks/...
  useListConversations(), useListMessages(), useCreateConversation(), useSendMessage(), useConversationWebSocket(id)
  useListNotifications(), useMarkRead()
  useSearch(), useListFiles(), useUploadFile(), useDeleteFile(), useAiQuery()
  Admin: useAdminStats(), useListUsers(), useListApplications(), useApproveApplication(), useRejectApplication(), useListFaqs(), useUpsertFaq(), useDeleteFaq()
"""


# ── Page intent registry ──────────────────────────────────────────────

# Each entry is a (kind_label, one-sentence-intent, design-hints) tuple.
# Match against file_path. First match wins.
_PAGE_INTENTS: tuple[tuple[str, str, str], ...] = (
    ("src/app/(auth)/login/", "login",
     "Quiet, focused sign-in card. Email + password fields, primary submit button, and a link to /register/[type] if public application is enabled."),
    ("src/app/(auth)/signup/", "signup",
     "Account creation card with email + password + confirmation. Surface validation errors inline."),
    ("src/app/(auth)/bootstrap/", "bootstrap",
     "First-run admin bootstrap. One-shot create-the-first-admin form with email + password. Show a banner explaining this can only run once."),
    ("src/app/register/[type]/", "register",
     "Public application intake. Render the participant type's profile fields by section using <Card>+section headings. Group required fields first; mark required with a small asterisk. Submit produces an application, not an account."),
    ("src/app/(dashboard)/dashboard/supply/", "supply-dashboard",
     "Supply role dashboard. KPI cards on top (listings, inquiries received, profile completeness), a 'Next steps' card with primary CTAs (Edit profile, Upload documents, Reply to inquiries), and a recent-activity list. Avoid pretending to show fake data — derive everything from the hooks already in scope; show empty states when arrays are empty."),
    ("src/app/(dashboard)/dashboard/demand/", "demand-dashboard",
     "Demand role dashboard. KPI cards (matches, conversations started, saved searches), a primary 'Find producers' CTA card linking to /search, and a recent-activity list. Same data discipline as supply: show real values from hooks; empty states when arrays are empty."),
    ("src/app/(dashboard)/admin/users/", "admin-users-list",
     "Admin users table. Use <Table>; columns: avatar+display_name, email, role badge, status badge, created_at relative, row actions in <DropdownMenu>. Add a search Input above the table and a 'New user' Button on the top-right header."),
    ("src/app/(dashboard)/admin/applications/", "admin-applications-list",
     "Pending applications. Card-grid OR table; each row: applicant email, type, submitted-at, summary, primary 'Approve' Button + secondary 'Reject' outline Button. Confirm destructive actions in a Dialog."),
    ("src/app/(dashboard)/admin/faqs/", "admin-faqs",
     "FAQ management. List existing FAQs in expandable cards; top-right 'Add FAQ' opens a Dialog with question + answer textarea fields. Per-row Edit + Delete actions."),
    ("src/app/(dashboard)/admin/ai/", "admin-ai-settings",
     "Admin AI/LLM configuration. Use <Tabs> for ('Provider', 'Embeddings', 'Prompts'). Each tab has a labelled form. Save button anchored at the bottom of each tab."),
    ("src/app/(dashboard)/admin/", "admin-dashboard",
     "Operational overview. KPI grid (Pending Applications, Total Users, Active Profiles, Open Conversations) using <Card>+CardHeader, then two columns: 'Recent applications' list + 'System health' list. Wire to useAdminStats."),
    ("src/app/(dashboard)/conversations/[id]/", "conversation-thread",
     "Chat thread. Header strip with the other party's name + status; message list scrolls; sticky <form> at bottom with auto-grow textarea and send <Button>. Use useListMessages + useConversationWebSocket. Distinguish own vs other messages by alignment + bg-primary/10 vs bg-muted."),
    ("src/app/(dashboard)/conversations/", "conversation-list",
     "Inbox view. Searchable list with avatar, last-message preview, unread badge, relative time on the right. Click navigates to /conversations/[id]. Empty state encourages starting via Search."),
    ("src/app/(dashboard)/notifications/", "notifications",
     "Notifications inbox. List grouped by 'Unread' / 'Earlier'; per-row: icon, title, body, action link, and a 'Mark read' ghost button (hooked via useMarkRead). Top-right 'Mark all read' Button."),
    ("src/app/(dashboard)/files/", "files-manager",
     "File manager. Card with a drop-zone <input type='file'> at the top, then a Table of uploads (name, size, uploaded_at, actions). Per-row download + delete (with Dialog confirmation)."),
    ("src/app/(dashboard)/ai/", "ai-chat",
     "AI assistant chat. Centered, max-w-3xl. Message list with role-styled bubbles; sticky bottom textarea + Send button. Stream-friendly layout (latest at bottom)."),
    ("src/app/(dashboard)/onboarding/", "onboarding-wizard",
     "Stepwise onboarding. Use <Tabs> as steps OR a numbered progress strip. Each step is a <Card> with the relevant fields; Back + Continue buttons. Final step submits."),
    ("src/app/(dashboard)/profile/edit/", "profile-edit",
     "Edit own profile. Use <ProfileForm> wired to useCurrentProfile + useUpdateMyProfile. Group fields by section using <Card>; sticky footer with Save + Discard buttons."),
    ("src/app/(dashboard)/profile/", "profile-view",
     "Own profile view. Header card: avatar, display name, role badge, completeness progress, Edit Profile primary CTA. Sections rendered as Cards; use FieldRenderer for individual fields."),
    ("src/app/(dashboard)/profiles/[id]/", "profile-detail",
     "Public profile detail. Hero card (avatar, name, role badge, location), 'Start conversation' primary CTA when permitted, then sections of public/protected fields rendered with <FieldRenderer>. Hide private/internal fields entirely."),
    ("src/app/(dashboard)/search/", "search",
     "Discovery / search. Top: search Input with submit button + filter chips for marketplace.discovery.filter_fields. Results: responsive grid of <ProfileCard>. Empty state with helpful suggestion."),
    ("src/components/layouts/app-sidebar.", "sidebar-nav",
     "Persistent left sidebar. Logo + marketplaceName at top; nav items mapped from navigationItems filtered by current user role; active route gets bg-accent text-accent-foreground; sign-out at bottom."),
    ("src/components/layouts/header.", "app-header",
     "Top bar. Left: page breadcrumb or marketplaceName on mobile. Right: notifications bell with unread Badge, then Avatar+DropdownMenu (Profile / Settings / Sign out)."),
    ("src/components/forms/profile-form.", "profile-form-component",
     "Reusable profile form. Receives a participant type slug and the IR fields-by-section. Render each section as a <Card>; render each field through <FieldRenderer>. Show error state with inline message; sticky footer with Save + Cancel."),
)


_DESIGN_CONTRACT = """\
## Design contract — apply on EVERY fill (this is non-negotiable)

VOICE: confident, plain, marketplace-professional. No marketing fluff.

VISUAL HIERARCHY
- Page title: <h1 className="text-3xl font-bold tracking-tight">; one-line subhead in text-muted-foreground beneath it.
- Section title: <h2 className="text-lg font-semibold">. Card title: <CardTitle>.
- Group related content into <Card>; do NOT use bare div.rounded-lg.border. Cards have CardHeader + CardContent.

LAYOUT & SPACING
- Top-level sections: space-y-6. Inside cards: space-y-4 (or space-y-3 for tight forms).
- Grids: prefer the breakpoint ladder `grid gap-4 sm:grid-cols-2 lg:grid-cols-3` (or 4 for KPI strips).
- Tables: <Table> from @/components/ui/table, never raw <table>. Lists: <ul className="divide-y rounded-md border">.
- Forms: vertical stack. Each field: <Label> + (Input|Select|Textarea). Group sections in Cards.

STATES — NEVER SKIP
- Loading: render <Skeleton> blocks that match the eventual layout; do NOT print "…" or "Loading...". For long lists, render 3–5 skeleton rows.
- Empty: a centered block with an icon (lucide-react), a one-line heading, a one-line subhead, and a primary <Button> CTA.
- Error: a Card with bg-destructive/10 border-destructive/30, lucide AlertCircle icon, message, and an outline <Button onClick={() => refetch?.()}>Try again</Button>.

ACTIONS
- Primary: <Button> default. Secondary: variant="outline". Destructive: variant="destructive". Tertiary: variant="ghost".
- Page-level primary action lives top-right in the header row, beside the title.
- Destructive confirmations use <Dialog>, not window.confirm.

MOTION — restrained, purposeful, fixed vocabulary
- Page-level mount: the dashboard layout already wraps each page in `animate-fade-in-up` — DO NOT add a second page-level animation.
- Cards on a fresh page: add `animate-fade-in-up` with a `style={{ animationDelay: "<n>ms" }}` cascade (60ms steps, max 240ms) so the page reveals top-to-bottom. Better still, wrap the section in `<Stagger>` from `@/lib/motion` and let it set the delays for direct children.
- Hover affordances: interactive Cards get `transition-all duration-200 ease-out-soft hover:-translate-y-0.5 hover:shadow-md`. Buttons get `transition-transform active:scale-[0.98]`.
- Loading-to-content swaps: render the success branch with `animate-fade-in` (no slide). Skeleton blocks use the built-in `animate-pulse`.
- Dialogs and dropdowns animate themselves through Radix — do NOT add classes there.
- Allowed animation utilities only: `animate-fade-in`, `animate-fade-in-up`, `animate-fade-in-down`, `animate-slide-in-right`, `animate-scale-in`, `animate-pulse`, plus the `<Reveal>` and `<Stagger>` wrappers from `@/lib/motion`. NEVER use `transform-gpu`, `will-change`, or hardcoded `@keyframes`.
- Static text and decorative icons: no animation. Animation is for state transitions and entry moments only.

DATA DISCIPLINE
- Never invent data. Use the variables, hooks, and props already in scope (see file content). If a list is empty, render the empty state instead of placeholder rows.
- A hook `.data` is typed as `unknown` in the generated client. NEVER call array methods (`.map`, `.filter`, `.slice`, `.length`) on it without a runtime guard. Use `Array.isArray(hook.data) ? hook.data as Array<T> : []` — the TypeScript `as Array<T>` cast does NOT enforce shape at runtime.
- The page facts list every backend hook this page is expected to wire under `hooks_to_wire`. Surface a real UI control (button, list, form, action menu) for each one whose UX fits the page intent — wiring an extra mutation is much better than leaving a backend endpoint unreachable.
- For badges that reflect status, map known values: pending→"secondary", approved→"default", rejected→"destructive", active→"default", inactive→"outline".
- Format dates via `new Date(x).toLocaleDateString()`; relative time only if a helper is in scope.

CODE STRUCTURE INSIDE THE MARKER BLOCK
- The block must be a JSX expression — NOT statements, function declarations, or IIFEs.
- DO NOT write `(() => { ... })()` inside the marker. If you need to use a filtered subset twice, just call `.filter(...)` twice inline; the cost is negligible and avoids unbalanced parens.
- DO NOT redeclare hooks or `const` bindings that already exist outside the marker.
- IDENTIFIER SCOPE for variables/state/handlers — strict: only reference variables, state setters, and helper functions that LITERALLY appear in the target file content shown below. If you want a piece of state (`expandedItems`, `editing`, `dialogOpen`) that the file does not declare, you cannot use it — instead, render the equivalent UI as inline conditionals on existing data (e.g., always-visible cards, anchor `<Link>`s, or `<details><summary>` for collapsibles) without new state.
- HOOK SCOPE — generous: you MAY freely call any hook listed under `hooks_to_wire` even if its import is not yet in the file's import block. The orchestrator auto-imports referenced hooks after your fill. Compose them at the top of the marker block as plain `const x = useXxx()` calls, then wire them into the JSX. Do NOT add `import` statements yourself — only call the hooks and let the orchestrator resolve them.
- Match the existing JSX nesting: every opening tag closes; every `{...}` JSX expression has a single `}`; every `(...)` group has a matching `)`.

TYPING — hook `.data` and `profile.fields` are `unknown`
- React Query / generated hooks expose `.data` as `unknown` and IR-driven profiles expose `.fields` as a record of unknowns. You CANNOT pass them to props that expect `string` / `ReactNode` directly — TypeScript will fail.
- Coerce at use site:
  * For string-typed props (Input/Select `value`, `placeholder`, attribute strings):
    `value={String((settings.data as Record<string, unknown> | null)?.provider ?? "openai")}`
  * For arrays returned by hooks:
    `((items.data as Array<{ id?: string; title?: string }> | undefined) ?? []).map(...)`
  * For boolean `cond && <JSX/>` guards on `unknown`:
    `{Boolean(profile.fields?.description) && (<div>...</div>)}`
  * For raw rendering of unknown text:
    `{String(profile.fields?.description ?? "")}`
- Prefer narrowing to `Record<string, unknown>` or a small inline type `{ field?: string; ... }` over `as any`.

ACCESSIBILITY & RESPONSIVENESS
- Every Input has a Label with htmlFor. Icon-only buttons get aria-label.
- Mobile-first: stack on small screens, expand at md/lg.
- Tab order should follow visual order; primary action is the last tab stop in a form.

OUTPUT PROTOCOL (strict)
- Return ONLY valid JSON: {"replacements":[{"id":"<marker_id>","content":"<tsx fragment>"}]}
- No markdown fences, no prose, no extra keys.
- Each `content` must be valid TSX that fits inside the existing marker boundaries — replacements must NOT redeclare hooks/imports already at the top of the file.
- Reference identifiers already declared in the file. Do NOT introduce new imports inside the marker block.
"""


def build_system_prompt(ir: FrontendIR) -> str:
    """Constant-per-run design contract for the Anthropic Claude system message."""
    voice = ir.theme.voice or "clear, professional marketplace voice"
    logo = ir.theme.logo_emoji or ""
    return "\n".join(
        [
            f"You are a senior frontend engineer filling AGENT_FILL stubs for {ir.marketplace.name},",
            f"a marketplace for {ir.marketplace.industry.lower()}: {ir.marketplace.description}",
            "",
            "## Brand voice — informs every label, button, microcopy, empty-state line",
            f"- Voice: {voice}",
            f"- Brand mark: {logo} {ir.marketplace.name}",
            f"- Theme palette is already wired via Tailwind tokens (`bg-primary`, `text-primary`,",
            "  `bg-accent`, `border-border`, `text-muted-foreground`, etc.). DO NOT hardcode hex colors",
            "  or Tailwind palette colors like `bg-blue-600` — always use the semantic tokens.",
            f"- Radius is themed via `rounded-md` / `rounded-lg`; respect the existing rounding.",
            "",
            "## UI inventory available in the project",
            _UI_INVENTORY,
            "",
            _DESIGN_CONTRACT,
        ]
    )


def derive_page_facts(file_path: str, ir: FrontendIR) -> str:
    """Per-file facts: page intent + (when relevant) entity field schema.

    The output is a Markdown-formatted block injected into the user message so
    the model has IR-grounded knowledge of the page it's filling.
    """
    lines: list[str] = []

    intent = _match_intent(file_path)
    if intent is not None:
        kind, blurb = intent
        lines.append(f"page_kind: `{kind}`")
        lines.append(f"page_intent: {blurb}")
    else:
        lines.append("page_kind: (unrecognized — infer from file body and stay consistent with the design contract)")

    entity = _entity_for_file(file_path, ir)
    if entity is not None:
        lines.append("")
        lines.append(f"entity: {entity.name} (slug=`{entity.slug}`, role=`{entity.role}`)")
        lines.append("entity_fields_by_section:")
        for section in entity.sections:
            lines.append(f"  - section: {section.name}")
            for field in section.fields:
                opts = ""
                if field.options:
                    opts = f", options=[{', '.join(field.options)}]"
                req = "required" if field.required else "optional"
                lines.append(
                    f"    * {field.name} — type={field.field_type}, "
                    f"label={field.label!r}, {req}, visibility={field.visibility}{opts}"
                )

    nav_routes = sorted({item.route for item in ir.navigation.items})
    if nav_routes:
        lines.append("")
        lines.append("nav_routes_available_for_links: " + ", ".join(nav_routes))

    relevant = _relevant_operations_for_page(file_path, ir)
    if relevant:
        lines.append("")
        lines.append(
            "hooks_to_wire (every backend endpoint relevant to this page — "
            "wire the ones that fit the UX, do NOT leave them all unused):"
        )
        for op in relevant:
            hook = _hook_name_for(op)
            lines.append(
                f"  * {hook}() — {op.method} {op.path}"
                + (f"  ({op.module})" if op.module else "")
            )

    return "\n".join(lines)


def build_fill_prompt(
    *,
    file_path: str,
    file_content: str,
    marker_ids: list[str],
    ir: FrontendIR,
    feedback: str | None = None,
    page_facts: str | None = None,
) -> str:
    """Build the per-file user message.

    The system prompt (``build_system_prompt``) carries the constant design
    contract; this user message carries only the per-file context.
    """
    header_context = {
        "marketplace": ir.marketplace.name,
        "marker_ids": marker_ids,
        "file_path": file_path,
        "all_pages": [p.id for p in ir.pages],
        "all_entities": [e.slug for e in ir.entities],
    }
    facts = page_facts if page_facts is not None else derive_page_facts(file_path, ir)
    lines: list[str] = [
        "## Task",
        f"Fill the AGENT_FILL marker(s) in `{file_path}`.",
        f"Marker IDs to replace: {marker_ids}",
        "",
        "## Page facts",
        facts,
        "",
        "## Run context",
        json.dumps(header_context, indent=2, sort_keys=True),
    ]
    if feedback:
        lines.extend(
            [
                "",
                "## Verification feedback from previous attempt — fix these issues",
                feedback.strip(),
            ]
        )
    lines.extend(
        [
            "",
            "## Target file content (preserve everything outside markers)",
            file_content,
        ]
    )
    return "\n".join(lines)


def prompt_hash(prompt: str) -> str:
    """Stable hash for tracking prompt provenance in manifest metadata."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


# ── helpers ───────────────────────────────────────────────────────────


def _match_intent(file_path: str) -> tuple[str, str] | None:
    for needle, kind, blurb in _PAGE_INTENTS:
        if needle in file_path:
            return kind, blurb
    return None


# Per-page → backend operations that page is responsible for surfacing in the UI.
# Each entry maps a file_path *needle* to a list of (method, path-pattern) match
# rules. ``{*}`` means "any path-parameter segment". The matcher is intentionally
# narrow (no wildcards across whole prefixes) so a page only sees ops it should
# actually wire, not the whole module.
_PAGE_OPERATION_RULES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("src/app/(auth)/login/", (("POST", "/api/auth/login"),)),
    ("src/app/(auth)/signup/", (("POST", "/api/auth/signup"),)),
    ("src/app/(auth)/bootstrap/", (("POST", "/api/auth/bootstrap"),)),
    ("src/app/register/[type]/", (
        ("POST", "/api/profiles/{type_slug}/register"),
        ("GET", "/api/profiles/{type_slug}/draft"),
        ("PUT", "/api/profiles/{type_slug}/draft"),
        ("POST", "/api/profiles/{type_slug}/draft/submit"),
    )),
    ("src/app/(dashboard)/onboarding/", (
        ("GET", "/api/profiles/{type_slug}/draft"),
        ("PUT", "/api/profiles/{type_slug}/draft"),
        ("POST", "/api/profiles/{type_slug}/draft/submit"),
    )),
    ("src/app/(dashboard)/profile/edit/", (
        ("GET", "/api/profiles/{type_slug}/me"),
        ("PUT", "/api/profiles/{type_slug}/{profile_id}"),
    )),
    ("src/app/(dashboard)/profile/", (
        ("GET", "/api/profiles/{type_slug}/me"),
    )),
    ("src/app/(dashboard)/profiles/[id]/", (
        ("GET", "/api/profiles/{type_slug}/{profile_id}"),
        ("POST", "/api/conversations"),
    )),
    ("src/app/(dashboard)/conversations/[id]/", (
        ("GET", "/api/conversations/{conv_id}"),
        ("GET", "/api/conversations/{conv_id}/messages"),
        ("POST", "/api/conversations/{conv_id}/messages"),
        ("PUT", "/api/conversations/{conv_id}/messages/{msg_id}"),
        ("DELETE", "/api/conversations/{conv_id}/messages/{msg_id}"),
        ("POST", "/api/conversations/{conv_id}/accept"),
        ("POST", "/api/conversations/{conv_id}/reject"),
        ("POST", "/api/conversations/{conv_id}/close"),
        ("POST", "/api/conversations/{conv_id}/share-assets"),
    )),
    ("src/app/(dashboard)/conversations/", (
        ("GET", "/api/conversations"),
        ("POST", "/api/conversations"),
    )),
    ("src/app/(dashboard)/notifications/", (
        ("GET", "/api/notifications"),
        ("PUT", "/api/notifications/{notification_id}/read"),
    )),
    ("src/app/(dashboard)/files/", (
        ("POST", "/api/files/upload"),
        ("GET", "/api/files/{file_id}"),
        ("DELETE", "/api/files/{file_id}"),
    )),
    ("src/app/(dashboard)/ai/", (
        ("POST", "/api/ai/query"),
        ("POST", "/api/ai/follow-up"),
        ("GET", "/api/ai/documents"),
        ("POST", "/api/ai/documents"),
        ("DELETE", "/api/ai/documents/{doc_id}"),
    )),
    ("src/app/(dashboard)/search/", (
        ("POST", "/api/search"),
        ("POST", "/api/search/{type_slug}"),
    )),
    ("src/app/(dashboard)/admin/users/", (
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/users/{user_id}"),
        ("POST", "/api/admin/users/{user_id}/activate"),
        ("POST", "/api/admin/users/{user_id}/deactivate"),
        ("PUT", "/api/admin/users/{user_id}/role"),
    )),
    ("src/app/(dashboard)/admin/applications/[id]/", (
        ("GET", "/api/admin/applications"),
        ("POST", "/api/admin/applications/{app_id}/approve"),
        ("POST", "/api/admin/applications/{app_id}/reject"),
    )),
    ("src/app/(dashboard)/admin/applications/", (
        ("GET", "/api/admin/applications"),
        ("POST", "/api/admin/applications/{app_id}/approve"),
        ("POST", "/api/admin/applications/{app_id}/reject"),
        ("GET", "/api/admin/profiles/{profile_id}"),
        ("PUT", "/api/admin/profiles/{profile_id}/status"),
    )),
    ("src/app/(dashboard)/admin/profiles/[id]/", (
        ("GET", "/api/admin/profiles/{profile_id}"),
        ("PUT", "/api/admin/profiles/{profile_id}/status"),
    )),
    ("src/app/(dashboard)/admin/conversations/[id]/", (
        ("GET", "/api/admin/conversations/{conversation_id}/messages"),
    )),
    ("src/app/(dashboard)/admin/conversations/", (
        ("GET", "/api/admin/conversations"),
    )),
    ("src/app/(dashboard)/admin/config/", (
        ("GET", "/api/admin/config"),
    )),
    ("src/app/(dashboard)/admin/faqs/", (
        ("GET", "/api/admin/faqs"),
        ("GET", "/api/admin/faqs/{faq_id}"),
        ("POST", "/api/admin/faqs"),
        ("PUT", "/api/admin/faqs/{faq_id}"),
        ("DELETE", "/api/admin/faqs/{faq_id}"),
    )),
    ("src/app/(dashboard)/admin/ai/", (
        ("GET", "/api/admin/ai/settings"),
        ("PUT", "/api/admin/ai/settings"),
        ("GET", "/api/admin/ai/providers"),
        ("POST", "/api/admin/ai/providers/validate"),
        ("GET", "/api/admin/ai/models"),
        ("GET", "/api/admin/ai/prompts"),
        ("PUT", "/api/admin/ai/prompts/{intent}"),
        ("GET", "/api/admin/ai/documents"),
        ("DELETE", "/api/admin/ai/documents/{doc_id}"),
    )),
    ("src/app/(dashboard)/admin/", (
        ("GET", "/api/admin/dashboard"),
        ("GET", "/api/admin/config"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/applications"),
        ("POST", "/api/admin/applications/{app_id}/approve"),
        ("POST", "/api/admin/applications/{app_id}/reject"),
        ("GET", "/api/admin/conversations"),
    )),
    ("src/app/(dashboard)/dashboard/supply/", (
        ("GET", "/api/conversations"),
        ("GET", "/api/notifications"),
        ("GET", "/api/profiles/{type_slug}/me"),
    )),
    ("src/app/(dashboard)/dashboard/demand/", (
        ("GET", "/api/conversations"),
        ("GET", "/api/notifications"),
        ("GET", "/api/profiles/{type_slug}/me"),
        ("POST", "/api/search"),
    )),
)


def _relevant_operations_for_page(file_path: str, ir: FrontendIR) -> list[OperationIR]:
    """Return the IR operations a page is expected to wire into its UI."""
    matchers: tuple[tuple[str, str], ...] = ()
    for needle, rules in _PAGE_OPERATION_RULES:
        if needle in file_path:
            matchers = rules
            break
    if not matchers:
        return []
    wanted = {(m.upper(), p) for m, p in matchers}
    found: list[OperationIR] = []
    for op in ir.operations:
        if (op.method.upper(), op.path) in wanted:
            found.append(op)
    return found


def _hook_name_for(op: OperationIR) -> str:
    """Mirror ``hooks_gen._derive_hook_name`` so the prompt names match
    what's actually exported from ``@/generated/hooks``.
    """
    base = op.id
    if base.startswith("get"):
        return f"use{base[3:]}"
    return f"use{base[0].upper()}{base[1:]}"


_REGISTER_TYPE_RE = re.compile(r"src/app/register/\[type\]/")


def _entity_for_file(file_path: str, ir: FrontendIR) -> EntityIR | None:
    """Pick the entity whose schema is most relevant to this file.

    - register/[type] page: render fields for any entity with public application
      enabled — return the first one as a representative example.
    - dashboard/supply or supply-related files: return any role=supply entity.
    - dashboard/demand: return any role=demand entity.
    - profile-form and profile pages: return the first entity (representative).
    """
    if _REGISTER_TYPE_RE.search(file_path):
        return ir.entities[0] if ir.entities else None
    if "/dashboard/supply/" in file_path:
        return next((e for e in ir.entities if e.role == "supply"), None)
    if "/dashboard/demand/" in file_path:
        return next((e for e in ir.entities if e.role == "demand"), None)
    if "profile-form" in file_path or "/profile/edit/" in file_path or "/profile/page" in file_path:
        return ir.entities[0] if ir.entities else None
    return None
