"""Entry point: python -m compiler

Usage:
    cd frontend
    python -m compiler generate \
        --openapi ../openapi/generated_openapi.json \
        --marketplace ../marketplace.yaml \
        --output .
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="compiler",
        description="Cosolvent Frontend Compiler — generate a Next.js app from OpenAPI + marketplace.yaml",
    )
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate", help="Generate Next.js frontend")
    gen_parser.add_argument(
        "--openapi",
        required=True,
        help="Path to OpenAPI spec (e.g. ../openapi/generated_openapi.json)",
    )
    gen_parser.add_argument(
        "--marketplace",
        required=True,
        help="Path to marketplace.yaml config",
    )
    gen_parser.add_argument(
        "--output",
        default=".",
        help="Output directory for generated files (default: current dir)",
    )
    gen_parser.add_argument(
        "--clean",
        action="store_true",
        help="Overwrite all files including user-modified ones",
    )
    gen_parser.add_argument(
        "--agent-fill",
        action="store_true",
        help="Run constrained LLM fill pass for AGENT_FILL markers",
    )
    gen_parser.add_argument(
        "--agent-model",
        default="anthropic/claude-sonnet-4",
        help="OpenRouter slug for agent fill (Anthropic Claude Sonnet family only)",
    )
    gen_parser.add_argument(
        "--agent-timeout-seconds",
        type=int,
        default=120,
        help="Timeout per agent fill request",
    )
    gen_parser.add_argument(
        "--verify-build",
        action="store_true",
        help="Run type-check/build verification after agent fill",
    )
    gen_parser.add_argument(
        "--check",
        action="store_true",
        help="Check manifest/spec hash sync without writing files",
    )

    args = parser.parse_args()

    if args.command == "generate":
        from .cli import run_generate_frontend

        ok = run_generate_frontend(
            openapi_path=args.openapi,
            marketplace_path=args.marketplace,
            output_dir=args.output,
            clean=bool(args.clean),
            agent_fill=bool(args.agent_fill),
            agent_model=args.agent_model,
            agent_timeout_seconds=int(args.agent_timeout_seconds),
            verify_build=bool(args.verify_build),
            check=bool(args.check),
        )
        sys.exit(0 if ok else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
