"""CLI handler for the frontend compiler."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

console = Console()


def run_generate_frontend(
    *,
    openapi_path: str,
    marketplace_path: str,
    output_dir: str = "frontend",
    clean: bool = False,
) -> bool:
    """Execute the frontend compiler and print results."""
    from .service import compile_frontend

    try:
        result = compile_frontend(
            openapi_path=openapi_path,
            marketplace_path=marketplace_path,
            output_dir=output_dir,
            clean=clean,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return False
    except ValueError as exc:
        console.print(f"[red]Validation error:[/red] {exc}")
        return False
    except Exception as exc:
        console.print(f"[red]Unexpected error:[/red] {exc}")
        return False

    console.print()
    console.print("[green]Frontend compiled successfully[/green]")
    console.print(f"  spec_hash: {result['spec_hash'][:16]}...")
    console.print(f"  output:    {result['output_dir']}")
    console.print()

    table = Table(title="Generated Files")
    table.add_column("Status", style="cyan", width=10)
    table.add_column("File", style="white")

    for f in result.get("generated", []):
        table.add_row("written", f)
    for f in result.get("skipped", []):
        table.add_row("skipped", f)
    for f in result.get("removed", []):
        table.add_row("removed", f)

    console.print(table)
    console.print(
        f"\n  [bold]{len(result.get('generated', []))}[/bold] written, "
        f"[bold]{len(result.get('skipped', []))}[/bold] skipped, "
        f"[bold]{len(result.get('removed', []))}[/bold] removed"
    )

    return True
