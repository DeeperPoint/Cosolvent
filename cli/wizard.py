"""7-step onboarding wizard orchestrator."""

from __future__ import annotations

from pathlib import Path

import questionary
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from app.core.marketplace_config import MarketplaceConfig
from cli.presets import PRESETS
from cli.steps.marketplace_identity import step_marketplace_identity
from cli.steps.participant_types import step_participant_types
from cli.steps.profile_schemas import step_profile_schemas
from cli.steps.onboarding_workflows import step_onboarding_workflows
from cli.steps.communication_rules import step_communication_rules
from cli.steps.discovery_config import step_discovery_config
from cli.steps.review_generate import step_review_generate

console = Console()


def run_wizard(output_path: str = "marketplace.yaml", preset_name: str | None = None) -> None:
    console.print(Panel.fit(
        "[bold blue]Cosolvent Marketplace Wizard[/bold blue]\n"
        "Configure your marketplace in 7 steps.",
        border_style="blue",
    ))

    config: dict | None = None

    # Try loading from preset
    if preset_name:
        if preset_name in PRESETS:
            config = PRESETS[preset_name]()
            console.print(f"\n[bold green]Loaded preset:[/] {preset_name}\n")
        else:
            console.print(f"\n[bold red]Unknown preset:[/] {preset_name}")
            return
    else:
        try:
            use_preset = questionary.confirm("Start from a preset?", default=False).ask()
        except KeyboardInterrupt:
            use_preset = False

        if use_preset:
            preset_choices = list(PRESETS.keys())
            try:
                chosen = questionary.select(
                    "Select a preset:",
                    choices=preset_choices,
                ).ask()
            except KeyboardInterrupt:
                chosen = None

            if chosen and chosen in PRESETS:
                config = PRESETS[chosen]()
                console.print(f"\n[bold green]Loaded preset:[/] {chosen}\n")

    # If no preset loaded, run interactive steps
    if config is None:
        config = {}

        # Step 1
        config["marketplace"] = step_marketplace_identity()

        # Step 2
        config["participant_types"] = step_participant_types()

        slugs = [pt["slug"] for pt in config["participant_types"]]

        # Step 3
        config["profile_schemas"] = step_profile_schemas(slugs)

        # Step 4
        config["onboarding"] = step_onboarding_workflows(slugs)

        # Step 5
        config["communication"] = step_communication_rules(config["participant_types"])

        # Step 6
        all_field_names = set()
        for schema in config["profile_schemas"].values():
            for section in schema["sections"]:
                for field in section["fields"]:
                    all_field_names.add(field["name"])
        config["discovery"] = step_discovery_config(slugs, list(all_field_names))

    # Step 7 — Review & confirm
    if step_review_generate(config):
        # Validate against MarketplaceConfig before writing
        try:
            MarketplaceConfig(**config)
        except ValidationError as exc:
            console.print("\n[bold red]Configuration validation failed:[/]\n")
            for error in exc.errors():
                loc = " -> ".join(str(l) for l in error["loc"])
                console.print(f"  [red]{loc}[/]: {error['msg']}")
            return

        path = Path(output_path)
        path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
        console.print(f"\n[bold green]Config written to {path}[/bold green]")
    else:
        console.print("\n[bold red]Wizard cancelled.[/bold red]")
