"""Step 3: Profile Schemas."""

from __future__ import annotations

import questionary
from rich.console import Console

console = Console()

FIELD_TYPES = ["text", "number", "select", "multi_select", "date", "file", "rich_text", "location"]
VISIBILITY_CHOICES = ["public", "protected", "private"]


def step_profile_schemas(slugs: list[str]) -> dict:
    console.print("\n[bold]Step 3/7: Profile Schemas[/bold]")
    schemas = {}

    for slug in slugs:
        console.print(f"\n[cyan]Profile schema for '{slug}':[/cyan]")
        sections = []

        while True:
            section_name = questionary.text(
                "Section name (or press Enter to finish):"
            ).ask()
            if not section_name:
                if not sections:
                    console.print("  [yellow]At least one section required.[/yellow]")
                    continue
                break

            fields = []
            while True:
                field_name = questionary.text(
                    f"  Field name in '{section_name}' (or Enter to finish):"
                ).ask()
                if not field_name:
                    break

                label = questionary.text(f"  Label for '{field_name}':").ask() or field_name
                ftype = questionary.select("  Type:", choices=FIELD_TYPES).ask()
                required = questionary.confirm("  Required?", default=False).ask()
                visibility = questionary.select("  Visibility:", choices=VISIBILITY_CHOICES).ask()
                searchable = questionary.confirm("  Searchable?", default=True).ask()

                field: dict = {
                    "name": field_name,
                    "label": label,
                    "type": ftype,
                    "required": required,
                    "visibility": visibility,
                    "searchable": searchable,
                }

                if ftype in ("select", "multi_select"):
                    opts = questionary.text("  Options (comma-separated):").ask()
                    field["options"] = [o.strip() for o in (opts or "").split(",") if o.strip()]

                fields.append(field)

            sections.append({"name": section_name, "fields": fields})

        schemas[slug] = {"sections": sections}

    return schemas
