"""Prompt builder for constrained AGENT_FILL second pass."""

from __future__ import annotations

import hashlib
import json

from .ir import FrontendIR


def build_fill_prompt(
    *,
    file_path: str,
    file_content: str,
    marker_ids: list[str],
    ir: FrontendIR,
    feedback: str | None = None,
) -> str:
    """Build a strict prompt asking for marker-only JSON replacements."""
    context = {
        "marketplace": ir.marketplace.name,
        "pages": [p.id for p in ir.pages],
        "entities": [e.slug for e in ir.entities],
        "marker_ids": marker_ids,
        "file_path": file_path,
    }
    lines: list[str] = [
        "You are filling UI stub markers in a generated Next.js file.",
        "Return ONLY valid JSON with this schema:",
        '{"replacements":[{"id":"<marker_id>","content":"<tsx code fragment>"}]}',
        "",
        "Hard constraints:",
        "- Do not include markdown fences.",
        "- Do not include keys besides `replacements`.",
        "- Only use marker IDs listed below.",
        "- Content must fit inside existing marker boundaries in the file.",
        "- Preserve imports and all code outside markers.",
        "",
        "Context:",
        json.dumps(context, indent=2, sort_keys=True),
    ]
    if feedback:
        lines.extend(
            [
                "",
                "Verification feedback from previous attempt:",
                feedback.strip(),
            ]
        )
    lines.extend(
        [
            "",
            "Target file content:",
            file_content,
        ]
    )
    return "\n".join(lines)


def prompt_hash(prompt: str) -> str:
    """Stable hash for tracking prompt provenance in manifest metadata."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
