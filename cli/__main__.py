"""Entry point: python -m cli"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cli",
        description="Cosolvent Marketplace CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # wizard subcommand
    wizard_parser = subparsers.add_parser("wizard", help="Run the setup wizard")
    wizard_parser.add_argument(
        "-o", "--output",
        default="marketplace.yaml",
        help="Output file path (default: marketplace.yaml)",
    )
    wizard_parser.add_argument(
        "-p", "--preset",
        choices=["agriculture", "professional_services"],
        help="Start from a preset configuration",
    )

    # validate subcommand
    validate_parser = subparsers.add_parser("validate", help="Validate a config file")
    validate_parser.add_argument(
        "file",
        nargs="?",
        default="marketplace.yaml",
        help="Config file to validate (default: marketplace.yaml)",
    )

    args = parser.parse_args()

    if args.command == "validate":
        from cli.validate import validate_config_file

        valid = validate_config_file(args.file)
        sys.exit(0 if valid else 1)
    else:
        # Default to wizard (no subcommand or explicit "wizard")
        from cli.wizard import run_wizard

        output = getattr(args, "output", "marketplace.yaml") or "marketplace.yaml"
        preset = getattr(args, "preset", None)
        run_wizard(output_path=output, preset_name=preset)


if __name__ == "__main__":
    main()
