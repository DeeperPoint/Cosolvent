from __future__ import annotations

import yaml
from rich.console import Console
from rich.syntax import Syntax

console = Console()


def step_review_generate(config: dict) -> None:
    console.print("\n[bold]Configuration Summary:[/]\n")

    yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
    syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=True)
    console.print(syntax)

    mp = config.get("marketplace", {})
    console.print(f"\n  Marketplace: [bold]{mp.get('name', 'N/A')}[/]")
    console.print(f"  Industry: {mp.get('industry', 'N/A')}")

    types = config.get("participant_types", [])
    console.print(f"  Participant types: {len(types)}")
    for pt in types:
        console.print(f"    - {pt['name']} ({pt['role']})")

    rules = config.get("communication", {}).get("conversation_rules", [])
    console.print(f"  Communication rules: {len(rules)}")
    for rule in rules:
        console.print(f"    - {rule['initiator']} -> {rule['receiver']}")

    console.print()
