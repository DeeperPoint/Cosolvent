"""Step 2: Participant Types."""

from __future__ import annotations

import re

import questionary
from rich.console import Console

console = Console()

ROLE_CHOICES = ["supply", "demand", "facilitator"]
PERMISSION_KEYS = [
    "can_list",
    "can_search",
    "can_initiate_conversation",
    "can_receive_conversation",
    "can_share_private_assets",
    "requires_onboarding",
    "requires_approval",
    "visible_in_search",
]


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def step_participant_types() -> list[dict]:
    console.print("\n[bold]Step 2/7: Participant Types[/bold]")
    console.print("Define 2-3 participant types (plus admin is automatic).\n")

    types = []
    for i in range(3):
        if i >= 2:
            add_more = questionary.confirm("Add a third participant type?", default=False).ask()
            if not add_more:
                break

        console.print(f"\n[cyan]Participant Type {i+1}:[/cyan]")
        name = questionary.text("Name (e.g., Producer, Buyer, Recruiter):").ask()
        if not name:
            break

        slug = _slugify(name)
        role = questionary.select("Role:", choices=ROLE_CHOICES).ask()

        console.print("  Permissions:")
        permissions = {}
        for key in PERMISSION_KEYS:
            default = _default_permission(key, role)
            val = questionary.confirm(f"    {key}?", default=default).ask()
            permissions[key] = val

        types.append({
            "name": name,
            "slug": slug,
            "role": role,
            "permissions": permissions,
        })

    return types


def _default_permission(key: str, role: str) -> bool:
    defaults = {
        "supply": {
            "can_list": True, "can_search": False, "can_initiate_conversation": False,
            "can_receive_conversation": True, "can_share_private_assets": True,
            "requires_onboarding": True, "requires_approval": True, "visible_in_search": True,
        },
        "demand": {
            "can_list": False, "can_search": True, "can_initiate_conversation": True,
            "can_receive_conversation": True, "can_share_private_assets": False,
            "requires_onboarding": True, "requires_approval": False, "visible_in_search": False,
        },
        "facilitator": {
            "can_list": False, "can_search": True, "can_initiate_conversation": True,
            "can_receive_conversation": True, "can_share_private_assets": False,
            "requires_onboarding": True, "requires_approval": True, "visible_in_search": False,
        },
    }
    return defaults.get(role, {}).get(key, False)
