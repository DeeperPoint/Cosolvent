"""Config file validation for CLI."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from rich.console import Console

from app.core.marketplace_config import load_marketplace_config

console = Console()


def validate_config_file(path: str) -> bool:
    """Validate a marketplace YAML config file.

    Returns True if valid, False otherwise.
    """
    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[bold red]Error:[/] File not found: {path}")
        return False

    try:
        config = load_marketplace_config(path)
        console.print(f"[bold green]Valid![/] Marketplace: [bold]{config.marketplace.name}[/]")
        console.print(f"  Industry: {config.marketplace.industry}")
        console.print(f"  Participant types: {', '.join(config.type_slugs())}")
        return True
    except ValidationError as exc:
        console.print("[bold red]Validation errors:[/]\n")
        for error in exc.errors():
            loc = " -> ".join(str(item) for item in error["loc"])
            console.print(f"  [red]{loc}[/]: {error['msg']}")
        return False
    except Exception as exc:
        console.print(f"[bold red]Error:[/] {exc}")
        return False
