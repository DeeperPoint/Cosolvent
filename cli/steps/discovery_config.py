"""Step 6: Discovery Configuration."""

from __future__ import annotations

import questionary
from rich.console import Console

console = Console()


def step_discovery_config(slugs: list[str], all_field_names: list[str]) -> dict:
    console.print("\n[bold]Step 6/7: Discovery Configuration[/bold]")

    searchable_types = questionary.checkbox(
        "Which types are searchable?", choices=slugs
    ).ask() or slugs[:1]

    filter_fields = []
    if all_field_names:
        filter_fields = questionary.checkbox(
            "Which fields should be filterable?", choices=sorted(all_field_names)
        ).ask() or []

    vector_search = questionary.confirm("Enable vector search (requires OpenAI)?", default=True).ask()
    rag_query = questionary.confirm("Enable RAG Q&A?", default=True).ask()
    follow_up = questionary.confirm("Enable follow-up suggestions?", default=True).ask()

    return {
        "searchable_types": searchable_types,
        "filter_fields": filter_fields,
        "result_visibility": {
            "anonymous": "public",
            "authenticated": "protected",
        },
        "ai": {
            "vector_search_enabled": vector_search,
            "rag_query_enabled": rag_query,
            "follow_up_suggestions": follow_up,
        },
    }
