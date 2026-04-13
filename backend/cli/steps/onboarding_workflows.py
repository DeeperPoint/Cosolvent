"""Step 4: Onboarding Workflows."""

from __future__ import annotations

import questionary
from rich.console import Console

console = Console()


def step_onboarding_workflows(slugs: list[str]) -> dict:
    console.print("\n[bold]Step 4/7: Onboarding Workflows[/bold]")
    onboarding = {}

    for slug in slugs:
        console.print(f"\n[cyan]Onboarding for '{slug}':[/cyan]")

        requires_approval = questionary.confirm("  Requires approval?", default=True).ask()
        approval_type = "manual"
        if requires_approval:
            approval_type = questionary.select(
                "  Approval type:", choices=["manual", "auto"]
            ).ask()

        doc_upload = questionary.confirm("  Document upload required?", default=False).ask()
        ai_extraction = False
        ai_profile_gen = False
        if doc_upload:
            ai_extraction = questionary.confirm("  AI extraction from documents?", default=False).ask()
        ai_profile_gen = questionary.confirm("  AI profile generation?", default=False).ask()
        welcome_email = questionary.confirm("  Welcome email on approval?", default=True).ask()
        threshold = int(questionary.text("  Profile completeness threshold (%):", default="100").ask() or 100)

        onboarding[slug] = {
            "requires_approval": requires_approval,
            "approval_type": approval_type,
            "document_upload_required": doc_upload,
            "ai_extraction_enabled": ai_extraction,
            "ai_profile_generation": ai_profile_gen,
            "welcome_email_on_approval": welcome_email,
            "profile_completeness_threshold": threshold,
        }

    return onboarding
