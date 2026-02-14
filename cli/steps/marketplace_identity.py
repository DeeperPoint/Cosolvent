"""Step 1: Marketplace Identity."""

from __future__ import annotations

import questionary
from rich.console import Console

console = Console()


def step_marketplace_identity() -> dict:
    console.print("\n[bold]Step 1/7: Marketplace Identity[/bold]")

    name = questionary.text("Marketplace name:").ask()
    description = questionary.text("Description:").ask()
    industry = questionary.text("Industry/vertical:").ask()

    return {
        "name": name or "My Marketplace",
        "description": description or "",
        "industry": industry or "",
    }
