"""Constrained agent fill pass for AGENT_FILL markers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from .agent_markers import apply_marker_replacements, find_fill_markers
from .agent_prompt import (
    build_fill_prompt,
    build_system_prompt,
    derive_page_facts,
    prompt_hash,
)
from .ir import FrontendIR

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default and policy: agent fill uses Anthropic **Sonnet** routes on OpenRouter only (no OpenAI slugs).
DEFAULT_AGENT_FILL_MODEL = "anthropic/claude-sonnet-4"

AGENT_FILL_PREFIXES = (
    "src/app/",
    "src/components/layouts/",
    "src/components/forms/",
    "src/components/shared/",
)


# Symbols the agent commonly references in fills and where they live.
# Used by ``_inject_missing_imports`` to back-fill imports the deterministic
# skeleton didn't anticipate.
_KNOWN_IMPORTS: dict[str, str] = {
    # shadcn/ui — components scaffolded into src/components/ui/*
    "Button": "@/components/ui/button",
    "Card": "@/components/ui/card",
    "CardContent": "@/components/ui/card",
    "CardDescription": "@/components/ui/card",
    "CardFooter": "@/components/ui/card",
    "CardHeader": "@/components/ui/card",
    "CardTitle": "@/components/ui/card",
    "Input": "@/components/ui/input",
    "Label": "@/components/ui/label",
    "Select": "@/components/ui/select",
    "SelectContent": "@/components/ui/select",
    "SelectGroup": "@/components/ui/select",
    "SelectItem": "@/components/ui/select",
    "SelectLabel": "@/components/ui/select",
    "SelectTrigger": "@/components/ui/select",
    "SelectValue": "@/components/ui/select",
    "Tabs": "@/components/ui/tabs",
    "TabsContent": "@/components/ui/tabs",
    "TabsList": "@/components/ui/tabs",
    "TabsTrigger": "@/components/ui/tabs",
    "Dialog": "@/components/ui/dialog",
    "DialogContent": "@/components/ui/dialog",
    "DialogDescription": "@/components/ui/dialog",
    "DialogFooter": "@/components/ui/dialog",
    "DialogHeader": "@/components/ui/dialog",
    "DialogTitle": "@/components/ui/dialog",
    "DialogTrigger": "@/components/ui/dialog",
    "DropdownMenu": "@/components/ui/dropdown-menu",
    "DropdownMenuContent": "@/components/ui/dropdown-menu",
    "DropdownMenuItem": "@/components/ui/dropdown-menu",
    "DropdownMenuLabel": "@/components/ui/dropdown-menu",
    "DropdownMenuSeparator": "@/components/ui/dropdown-menu",
    "DropdownMenuTrigger": "@/components/ui/dropdown-menu",
    "Avatar": "@/components/ui/avatar",
    "AvatarFallback": "@/components/ui/avatar",
    "AvatarImage": "@/components/ui/avatar",
    "Badge": "@/components/ui/badge",
    "Separator": "@/components/ui/separator",
    "Skeleton": "@/components/ui/skeleton",
    "Table": "@/components/ui/table",
    "TableBody": "@/components/ui/table",
    "TableCaption": "@/components/ui/table",
    "TableCell": "@/components/ui/table",
    "TableHead": "@/components/ui/table",
    "TableHeader": "@/components/ui/table",
    "TableRow": "@/components/ui/table",
}

# Lucide icon names allowed for auto-import. Any unknown PascalCase symbol the
# agent references that's also in this set will be imported from lucide-react.
_LUCIDE_ICONS: frozenset[str] = frozenset(
    {
        "Activity", "AlertCircle", "AlertTriangle", "ArrowDown", "ArrowLeft",
        "ArrowRight", "ArrowUp", "Bell", "Bookmark", "Calendar", "Check",
        "CheckCircle", "CheckCircle2", "ChevronDown", "ChevronLeft",
        "ChevronRight", "ChevronUp", "Circle", "Clock", "Copy", "Download",
        "Edit", "Edit2", "Edit3", "ExternalLink", "Eye", "EyeOff", "File",
        "FileText", "Filter", "FolderOpen", "Gauge", "Globe", "Heart",
        "HelpCircle", "Home", "Image", "Inbox", "Info", "LayoutDashboard",
        "Link", "Link2", "Loader", "Loader2", "Lock", "LogIn", "LogOut",
        "Mail", "MapPin", "Menu", "MessageCircle", "MessageSquare", "Mic",
        "Minus", "MoreHorizontal", "MoreVertical", "Package", "Paperclip",
        "Pencil", "Phone", "Plus", "PlusCircle", "RefreshCw", "Save",
        "Search", "Send", "Settings", "Share", "Share2", "Shield",
        "ShoppingCart", "Sparkles", "Square", "Star", "Tag", "Terminal",
        "ThumbsUp", "Trash", "Trash2", "TrendingUp", "Upload", "User",
        "UserPlus", "Users", "Wallet", "X", "XCircle", "Zap",
    }
)


_IMPORT_BLOCK_RE = re.compile(r'^import .+;[ \t]*$', re.MULTILINE)
_NAMED_IMPORT_RE = re.compile(r'import\s*\{([^}]+)\}\s*from\s*"[^"]+";')
_DEFAULT_IMPORT_RE = re.compile(r'import\s+(\w+)\s+from\s*"[^"]+";')
_USE_CLIENT_RE = re.compile(r'^"use client";[ \t]*\n', re.MULTILINE)
_JSX_TAG_RE = re.compile(r"<([A-Z][A-Za-z0-9_]*)")


def _inject_missing_imports(file_content: str) -> str:
    """Add imports for any known shadcn/lucide symbol the agent referenced.

    The agent fill is told it cannot edit imports inside the marker block, so
    this post-processor extends the existing top-of-file import group with
    anything the new content needs. Unknown symbols are left alone — the type
    checker will flag them as before.
    """
    used: set[str] = set(_JSX_TAG_RE.findall(file_content))
    for name in _LUCIDE_ICONS:
        if re.search(rf"\b{name}\b", file_content):
            used.add(name)

    existing: set[str] = set()
    for m in _NAMED_IMPORT_RE.finditer(file_content):
        for raw in m.group(1).split(","):
            sym = raw.strip().split(" as ")[0].strip()
            if sym:
                existing.add(sym)
    for m in _DEFAULT_IMPORT_RE.finditer(file_content):
        existing.add(m.group(1))

    missing_by_module: dict[str, set[str]] = {}
    for sym in used - existing:
        if sym in _KNOWN_IMPORTS:
            missing_by_module.setdefault(_KNOWN_IMPORTS[sym], set()).add(sym)
        elif sym in _LUCIDE_ICONS:
            missing_by_module.setdefault("lucide-react", set()).add(sym)

    if not missing_by_module:
        return file_content

    new_lines = [
        f'import {{ {", ".join(sorted(symbols))} }} from "{module}";'
        for module, symbols in sorted(missing_by_module.items())
    ]
    new_block = "\n".join(new_lines)

    last_import = None
    for m in _IMPORT_BLOCK_RE.finditer(file_content):
        last_import = m
    if last_import is not None:
        end = last_import.end()
        return file_content[:end] + "\n" + new_block + file_content[end:]

    use_client = _USE_CLIENT_RE.search(file_content)
    if use_client is not None:
        end = use_client.end()
        return file_content[:end] + "\n" + new_block + "\n" + file_content[end:]

    return new_block + "\n\n" + file_content


@dataclass(frozen=True)
class AgentFillOptions:
    enabled: bool = False
    model: str = DEFAULT_AGENT_FILL_MODEL
    timeout_seconds: int = 120


@dataclass(frozen=True)
class AgentFillResult:
    artifacts: dict[str, str]
    filled_files: list[str]
    prompt_hash: str | None


def _normalize_openrouter_api_key(key: str) -> str:
    """Strip junk that often sneaks in from ``.env`` (BOM, CRLF, quotes)."""
    s = (key or "").strip().replace("\ufeff", "")
    s = s.replace("\r", "").replace("\n", "")
    while len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s.strip()


def _read_dotenv_value(env_path: Path, key: str) -> str | None:
    """Parse a single ``KEY=value`` from a .env file (no dependency on python-dotenv)."""
    if not env_path.is_file():
        return None
    prefix = f"{key}="
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if not value:
            return None
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        return value.strip() or None
    return None


def _maybe_hydrate_openrouter_api_key_from_dotenv() -> None:
    """If ``OPENROUTER_API_KEY`` is unset, try common ``.env`` locations (local dev)."""
    if (os.getenv("OPENROUTER_API_KEY") or "").strip():
        return
    # ``frontend/compiler/frontend_agent.py`` → repo root is parents[2]
    repo_root = Path(__file__).resolve().parents[2]
    for env_path in (
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
        repo_root / ".env",
    ):
        val = _read_dotenv_value(env_path, "OPENROUTER_API_KEY")
        if val:
            os.environ["OPENROUTER_API_KEY"] = _normalize_openrouter_api_key(val)
            return


def _validate_agent_fill_model(model: str) -> None:
    """Agent fill is limited to Anthropic Claude **Sonnet** models on OpenRouter."""
    slug = model.strip().lower()
    if not slug.startswith("anthropic/claude-"):
        raise ValueError(
            "Agent fill only supports Anthropic Claude models on OpenRouter (Sonnet family). "
            f"Use e.g. {DEFAULT_AGENT_FILL_MODEL}. Got: {model!r}"
        )
    if "sonnet" not in slug:
        raise ValueError(
            "Agent fill only supports Sonnet-family models; the slug must contain 'sonnet'. "
            f"Examples: {DEFAULT_AGENT_FILL_MODEL}, anthropic/claude-3.7-sonnet. Got: {model!r}"
        )


def run_agent_fill(
    artifacts: dict[str, str],
    ir: FrontendIR,
    options: AgentFillOptions,
    *,
    feedback: str | None = None,
) -> AgentFillResult:
    """Run second-pass marker fill over eligible artifacts."""
    if not options.enabled:
        return AgentFillResult(dict(artifacts), [], None)

    _validate_agent_fill_model(options.model)

    _maybe_hydrate_openrouter_api_key_from_dotenv()
    api_key = _normalize_openrouter_api_key(os.getenv("OPENROUTER_API_KEY") or "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required when --agent-fill is enabled")
    os.environ["OPENROUTER_API_KEY"] = api_key

    updated = dict(artifacts)
    filled: list[str] = []
    prompt_hashes: list[str] = []

    system_prompt = build_system_prompt(ir)

    for path in sorted(updated):
        if not _eligible_for_fill(path):
            continue
        content = updated[path]
        markers = find_fill_markers(content)
        if not markers:
            continue

        marker_ids = [m.marker_id for m in markers]
        page_facts = derive_page_facts(path, ir)
        prompt = build_fill_prompt(
            file_path=path,
            file_content=content,
            marker_ids=marker_ids,
            ir=ir,
            feedback=feedback,
            page_facts=page_facts,
        )
        prompt_hashes.append(prompt_hash(system_prompt + "\n" + prompt))
        response_text = _call_openrouter(
            prompt=prompt,
            system_prompt=system_prompt,
            model=options.model,
            api_key=api_key,
            timeout=options.timeout_seconds,
        )
        parsed = _parse_response_json(response_text)
        replacements = {
            str(item["id"]): str(item["content"])
            for item in parsed.get("replacements", [])
            if isinstance(item, dict) and "id" in item and "content" in item
        }
        replaced = apply_marker_replacements(content, replacements)
        updated[path] = _inject_missing_imports(replaced)
        filled.append(path)

    combined_hash = None
    if prompt_hashes:
        combined_hash = prompt_hash("\n".join(sorted(prompt_hashes)))
    return AgentFillResult(updated, sorted(filled), combined_hash)


def _eligible_for_fill(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in AGENT_FILL_PREFIXES)


def _call_openrouter(
    *,
    prompt: str,
    model: str,
    api_key: str,
    timeout: int,
    system_prompt: str | None = None,
) -> str:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": messages,
        # Constrain providers that support JSON mode (Anthropic via OpenRouter does).
        # Reduces — but does not eliminate — structural malformation in long outputs.
        "response_format": {"type": "json_object"},
    }
    req = urlrequest.Request(
        OPENROUTER_CHAT_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except urlerror.HTTPError as exc:  # pragma: no cover - network path
        detail = exc.read().decode("utf-8", errors="ignore")
        msg = f"OpenRouter HTTP {exc.code}: {detail[:500]}"
        if exc.code == 401 and "Missing Authentication header" in detail:
            msg += (
                "\n\nNote: OpenRouter returns this message for many auth failures, not only "
                "a missing header. `GET /api/v1/models` succeeds even with an invalid key, so "
                "test your key with a small `POST /api/v1/chat/completions` request. Also check "
                "OPENROUTER_API_KEY for stray quotes, BOM, or line breaks in `.env`."
            )
        if exc.code == 404 and "No endpoints found for" in detail:
            msg += (
                "\n\nThat model slug is not available on OpenRouter (renamed or retired). "
                f"Pick a current Anthropic Sonnet id (e.g. {DEFAULT_AGENT_FILL_MODEL}) from "
                "https://openrouter.ai/models"
            )
        raise ValueError(msg) from exc
    except urlerror.URLError as exc:  # pragma: no cover - network path
        raise ValueError(f"OpenRouter request failed: {exc}") from exc

    content = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if not isinstance(content, str) or not content.strip():
        raise ValueError("OpenRouter returned empty content for agent fill")
    return content


def _parse_response_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Models occasionally trail or duplicate braces in long generations.
        # First try the largest balanced-brace prefix.
        repaired = _extract_balanced_json_object(text)
        if repaired is not None:
            try:
                parsed = json.loads(repaired)
            except json.JSONDecodeError:
                parsed = None
        # Fall back to extracting replacement entries directly via a
        # string-aware regex. This survives an extra ``}`` near the end
        # of a long content string, which is the most common failure.
        if parsed is None:
            entries = _salvage_replacement_entries(text)
            if entries:
                parsed = {"replacements": entries}
    if parsed is None:
        raise ValueError("Agent fill response is not valid JSON")
    if not isinstance(parsed, dict):
        raise ValueError("Agent fill response must be a JSON object")
    if "replacements" not in parsed:
        raise ValueError("Agent fill response missing 'replacements'")
    if not isinstance(parsed["replacements"], list):
        raise ValueError("'replacements' must be a list")
    return parsed


_REPLACEMENT_ENTRY_RE = re.compile(
    r'\{\s*"id"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"\s*,'
    r'\s*"content"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}',
    re.DOTALL,
)


def _salvage_replacement_entries(text: str) -> list[dict[str, str]]:
    """Best-effort extraction of ``{"id":..., "content":...}`` entries.

    Used when the outer JSON is malformed (e.g. a stray trailing brace).
    Each capture group is a JSON-string-literal body, so we wrap it back in
    quotes and let ``json.loads`` decode the escapes.
    """
    entries: list[dict[str, str]] = []
    for match in _REPLACEMENT_ENTRY_RE.finditer(text):
        try:
            entry_id = json.loads(f'"{match.group(1)}"')
            content = json.loads(f'"{match.group(2)}"')
        except json.JSONDecodeError:
            continue
        entries.append({"id": entry_id, "content": content})
    return entries


def _extract_balanced_json_object(text: str) -> str | None:
    """Return the substring spanning the first balanced top-level ``{...}``.

    Scans for matching braces while tracking JSON string state so quoted
    braces don't throw off the depth counter. Returns ``None`` when no
    balanced object is found.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None
