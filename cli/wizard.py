"""7-step onboarding wizard orchestrator."""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel

from cli.steps.marketplace_identity import step_marketplace_identity
from cli.steps.participant_types import step_participant_types
from cli.steps.profile_schemas import step_profile_schemas
from cli.steps.onboarding_workflows import step_onboarding_workflows
from cli.steps.communication_rules import step_communication_rules
from cli.steps.discovery_config import step_discovery_config
from cli.steps.review_generate import step_review_generate

console = Console()


def run_wizard(output_path: str = "marketplace.yaml") -> None:
    console.print(Panel.fit(
        "[bold blue]Cosolvent Marketplace Wizard[/bold blue]\n"
        "Configure your marketplace in 7 steps.",
        border_style="blue",
    ))

    config: dict = {}

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

    # Step 7
    if step_review_generate(config):
        path = Path(output_path)
        path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
        console.print(f"\n[bold green]Config written to {path}[/bold green]")
    else:
        console.print("\n[bold red]Wizard cancelled.[/bold red]")
