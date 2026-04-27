"""Augment generated page files with imports + ``const`` declarations for
every hook a page is supposed to wire (per ``_PAGE_OPERATION_RULES``).

The marker contract requires the AGENT_FILL block to be a JSX expression, so
hooks cannot be declared inside the block. This pass declares them in the
function body BEFORE the marker, putting them in scope for the agent fill.

Runs deterministically before the agent fill loop:

  emit_* → augment_pages_with_relevant_hooks → (agent fill) → write
"""

from __future__ import annotations

import re

from ..agent_prompt import _hook_name_for, _relevant_operations_for_page
from ..ir import FrontendIR, OperationIR


_HOOK_EXPORT_RE = re.compile(
    r"^export\s+(?:async\s+)?function\s+(use\w+)", re.MULTILINE
)
_NAMED_IMPORT_RE = re.compile(
    r'import\s*\{([^}]+)\}\s*from\s*"([^"]+)";', re.DOTALL
)
_LAST_IMPORT_RE = re.compile(r"^import .+?;\s*$", re.MULTILINE | re.DOTALL)
_HOOK_CALL_RE = re.compile(r"=\s*(use[A-Z]\w*)\s*\(")
_FUNCTION_OPEN_RE = re.compile(
    r"export\s+default\s+function\s+\w+\s*\([^)]*\)\s*\{"
)
# Identify the first line in the function body that ends "top-level setup" —
# a control flow / helper-function line. Hook declarations must come before
# this point so they run on every render path and stay above early returns.
_BODY_BARRIER_RE = re.compile(
    r"^  (?:if\s*\(|return\b|async\s+function\s+\w+|function\s+\w+|switch\s*\()",
    re.MULTILINE,
)
_BODY_RETURN_RE = re.compile(r"^\s*return\s*\(", re.MULTILINE)


# Local var name for a hook. Convention follows existing skeletons:
# - drop ``use`` prefix
# - lowercase first letter
# - rewrite reserved-word names so they don't collide with JS keywords
_LOCAL_NAME_OVERRIDES: dict[str, str] = {
    "useDeleteFaq": "removeFaq",
    "useDeleteFile": "removeFile",
    "useDeleteMessage": "removeMessage",
    "useDeleteDocument": "removeDocument",
    "useDeleteAdminDocument": "removeAdminDocument",
    "useUploadFile": "uploadFile",
    "useUploadDocument": "uploadDocument",
    "useEditMessage": "editMessage",
    "useSendMessage": "sendMessage",
    "useShareAssets": "shareAssets",
    "useAcceptConversation": "acceptConversation",
    "useRejectConversation": "rejectConversation",
    "useCloseConversation": "closeConversation",
}

_JS_RESERVED = {
    "delete", "class", "default", "new", "return", "for", "if", "else",
    "switch", "case", "break", "continue", "function", "var", "let", "const",
    "this", "super", "import", "export", "throw", "try", "catch", "finally",
    "yield", "void", "true", "false", "null", "undefined",
}


def _local_name(hook: str) -> str:
    if hook in _LOCAL_NAME_OVERRIDES:
        return _LOCAL_NAME_OVERRIDES[hook]
    body = hook[3:] if hook.startswith("use") else hook
    if not body:
        return hook
    name = body[0].lower() + body[1:]
    if name in _JS_RESERVED:
        name = name + "Action"
    return name


def augment_pages_with_relevant_hooks(
    artifacts: dict[str, str], ir: FrontendIR
) -> dict[str, str]:
    """Inject imports + ``const x = useX()`` for each page's wired hooks.

    Idempotent: re-running on already-augmented files leaves them unchanged.
    """
    hook_to_module = _build_hook_to_module_map(artifacts)
    if not hook_to_module:
        return artifacts

    augmented = dict(artifacts)
    for path, content in artifacts.items():
        if not (path.startswith("src/app/") and path.endswith("/page.tsx")):
            continue
        relevant = _relevant_operations_for_page(path, ir)
        if not relevant:
            continue
        wanted: list[tuple[str, OperationIR]] = []
        for op in relevant:
            hook = _hook_name_for(op)
            if hook in hook_to_module:
                wanted.append((hook, op))
        if not wanted:
            continue
        augmented[path] = _augment_one(content, wanted, hook_to_module)
    return augmented


def _build_hook_to_module_map(artifacts: dict[str, str]) -> dict[str, str]:
    """Map every exported ``useXxx`` to its ``@/generated/hooks/...`` module."""
    out: dict[str, str] = {}
    for path, content in artifacts.items():
        if not path.startswith("src/generated/hooks/") or not path.endswith(".ts"):
            continue
        module = "@/" + path[len("src/") :].removesuffix(".ts")
        for hook in _HOOK_EXPORT_RE.findall(content):
            out[hook] = module
    return out


def _augment_one(
    content: str,
    wanted: list[tuple[str, OperationIR]],
    hook_to_module: dict[str, str],
) -> str:
    imported = _imported_named_symbols(content)
    declared = set(_HOOK_CALL_RE.findall(content))

    missing = [
        (hook, op)
        for hook, op in wanted
        if hook not in imported and hook not in declared
    ]
    if not missing:
        return content

    content = _ensure_imports(content, [h for h, _ in missing], hook_to_module)
    content = _ensure_declarations(content, missing, declared)
    return content


def _imported_named_symbols(content: str) -> set[str]:
    out: set[str] = set()
    for m in _NAMED_IMPORT_RE.finditer(content):
        for raw in m.group(1).split(","):
            sym = raw.strip().split(" as ")[0].strip()
            if sym:
                out.add(sym)
    return out


def _ensure_imports(
    content: str, missing: list[str], hook_to_module: dict[str, str]
) -> str:
    by_module: dict[str, list[str]] = {}
    for h in missing:
        by_module.setdefault(hook_to_module[h], []).append(h)

    extra_imports: list[str] = []
    for module, hooks_list in sorted(by_module.items()):
        # Match an import statement targeting this exact module — DOTALL so
        # multi-line braces work. Use a fresh regex per module to keep groups
        # simple.
        pattern = re.compile(
            r'import\s*\{([^}]+)\}\s*from\s*"' + re.escape(module) + r'";',
            re.DOTALL,
        )
        match = pattern.search(content)
        if match:
            existing = {s.strip() for s in match.group(1).split(",") if s.strip()}
            merged = sorted(existing | set(hooks_list))
            replacement = (
                "import {\n  " + ",\n  ".join(merged) + ",\n} from \"" + module + "\";"
            )
            content = content[: match.start()] + replacement + content[match.end() :]
        else:
            extra_imports.append(
                'import { ' + ", ".join(sorted(set(hooks_list))) + ' } from "' + module + '";'
            )

    if extra_imports:
        # Insert after the last existing import (any module).
        last = None
        for m in re.finditer(r"^import .+?;\s*$", content, re.MULTILINE | re.DOTALL):
            last = m
        if last is not None:
            end = last.end()
            content = (
                content[:end] + "\n" + "\n".join(extra_imports) + content[end:]
            )
        else:
            content = "\n".join(extra_imports) + "\n" + content

    return content


def _ensure_declarations(
    content: str,
    missing: list[tuple[str, OperationIR]],
    already_declared: set[str],
) -> str:
    decls: list[str] = []
    used_locals = _existing_local_names(content)

    for hook, op in missing:
        if hook in already_declared:
            continue
        name = _local_name(hook)
        # Bump the local name if it would collide with an existing binding.
        original = name
        suffix = 2
        while name in used_locals:
            name = f"{original}{suffix}"
            suffix += 1
        used_locals.add(name)

        call_args = _hook_call_args(op)
        decls.append(f"  const {name} = {hook}({call_args});")

    if not decls:
        return content

    decls_block = "\n".join(decls)

    fn_match = _FUNCTION_OPEN_RE.search(content)
    if fn_match is None:
        return content
    body_start = fn_match.end()
    body = content[body_start:]
    barrier = _BODY_BARRIER_RE.search(body)
    if barrier is None:
        # No control flow / helper found — fall back to the final return.
        barrier = _BODY_RETURN_RE.search(body)
    if barrier is None:
        return content
    insert_at = body_start + barrier.start()

    return content[:insert_at] + decls_block + "\n\n" + content[insert_at:]


def _existing_local_names(content: str) -> set[str]:
    """Pull every binding the function body already declares, including
    destructured ``const [a, b]`` and ``const { a, b }`` patterns.
    """
    names: set[str] = set()
    for m in re.finditer(r"\bconst\s+(\w+)\s*=", content):
        names.add(m.group(1))
    for m in re.finditer(r"\bconst\s+\[\s*([^\]]+)\]\s*=", content):
        for piece in m.group(1).split(","):
            sym = piece.strip().split(":")[0].strip().split("=")[0].strip()
            if sym and sym.isidentifier():
                names.add(sym)
    for m in re.finditer(r"\bconst\s+\{\s*([^}]+)\}\s*=", content):
        for piece in m.group(1).split(","):
            sym = piece.strip().split(":")[-1].strip().split("=")[0].strip()
            if sym and sym.isidentifier():
                names.add(sym)
    return names


def _hook_call_args(op: OperationIR) -> str:
    """Emit the argument list for a hook call.

    - GET with path params: pass an empty string so the hook is type-safe and
      its ``enabled: Boolean(arg)`` gate keeps it inactive until rewired.
    - Mutations and arg-less queries: no args.
    """
    if op.method == "GET" and op.path_params:
        return ", ".join('""' for _ in op.path_params)
    return ""
