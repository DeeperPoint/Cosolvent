"""Step 5: Communication Rules."""

from __future__ import annotations

import questionary
from rich.console import Console

console = Console()


def step_communication_rules(participant_types: list[dict]) -> dict:
    console.print("\n[bold]Step 5/7: Communication Rules[/bold]")
    console.print("Define which types can initiate conversations with which.\n")

    slugs = [pt["slug"] for pt in participant_types]
    rules = []

    while True:
        initiator = questionary.select(
            "Initiator type (or Ctrl+C to finish):", choices=slugs + ["(done)"]
        ).ask()
        if initiator == "(done)":
            break

        receiver_choices = [s for s in slugs if s != initiator]
        if not receiver_choices:
            continue
        receiver = questionary.select("Receiver type:", choices=receiver_choices).ask()
        requires_approval = questionary.confirm("Requires approval?", default=True).ask()

        rules.append({
            "initiator": initiator,
            "receiver": receiver,
            "requires_approval": requires_approval,
        })

        console.print(f"  [green]Added: {initiator} → {receiver} (approval={requires_approval})[/green]")

        if not questionary.confirm("Add another rule?", default=True).ask():
            break

    return {"conversation_rules": rules}
