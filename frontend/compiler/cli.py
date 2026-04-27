"""CLI handler for the frontend compiler."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()


def run_generate_frontend(
    *,
    openapi_path: str,
    marketplace_path: str,
    output_dir: str = "frontend",
    clean: bool = False,
    agent_fill: bool = False,
    agent_model: str = "anthropic/claude-sonnet-4",
    agent_timeout_seconds: int = 120,
    verify_build: bool = False,
    check: bool = False,
) -> bool:
    """Execute the frontend compiler and print results."""
    from .service import compile_frontend

    try:
        result = compile_frontend(
            openapi_path=openapi_path,
            marketplace_path=marketplace_path,
            output_dir=output_dir,
            clean=clean,
            agent_fill=agent_fill,
            agent_model=agent_model,
            agent_timeout_seconds=agent_timeout_seconds,
            verify_build=verify_build,
            check=check,
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
    status = "Frontend check passed" if check else "Frontend compiled successfully"
    console.print(f"[green]{status}[/green]")
    console.print(f"  spec_hash: {result['spec_hash'][:16]}...")
    console.print(f"  output:    {result['output_dir']}")
    if result.get("agent_fill_enabled"):
        console.print(f"  agent_fill: enabled ({result.get('agent_model', 'unknown model')})")
    if result.get("verify_requested"):
        status = "passed" if result.get("verified") else "failed"
        console.print(f"  verification: {status}")
    if (not result.get("verified")) and result.get("verification_errors"):
        console.print(f"  verification_errors: {result['verification_errors']}")
    console.print()

    table = Table(title="Generated Files")
    table.add_column("Status", style="cyan", width=10)
    table.add_column("File", style="white")

    for f in result.get("generated", []):
        table.add_row("written", escape(f))
    for f in result.get("skipped", []):
        table.add_row("skipped", escape(f))
    for f in result.get("removed", []):
        table.add_row("removed", escape(f))

    console.print(table)
    console.print(
        f"\n  [bold]{len(result.get('generated', []))}[/bold] written, "
        f"[bold]{len(result.get('skipped', []))}[/bold] skipped, "
        f"[bold]{len(result.get('removed', []))}[/bold] removed"
    )

    return True
