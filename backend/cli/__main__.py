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

    # compile subcommand
    compile_parser = subparsers.add_parser("compile", help="Generate marketplace artifacts")
    compile_parser.add_argument(
        "--config",
        default="marketplace.yaml",
        help="Config file path (default: marketplace.yaml)",
    )
    compile_parser.add_argument(
        "--mode",
        choices=["mvp", "strict"],
        default="mvp",
        help="Generation mode (default: mvp)",
    )
    compile_parser.add_argument(
        "--check",
        action="store_true",
        help="Check generated artifacts are in sync without modifying files",
    )
    compile_parser.add_argument(
        "--export",
        action="store_true",
        help="Also create export archive",
    )
    compile_parser.add_argument(
        "--export-dir",
        default="exports",
        help="Export directory (default: exports)",
    )

    # export subcommand
    export_parser = subparsers.add_parser("export", help="Generate artifacts and create export archive")
    export_parser.add_argument(
        "--config",
        default="marketplace.yaml",
        help="Config file path (default: marketplace.yaml)",
    )
    export_parser.add_argument(
        "--mode",
        choices=["mvp", "strict"],
        default="mvp",
        help="Generation mode (default: mvp)",
    )
    export_parser.add_argument(
        "--export-dir",
        default="exports",
        help="Export directory (default: exports)",
    )

    # generate-config subcommand — build marketplace.yaml from a domain schema
    gen_parser = subparsers.add_parser(
        "generate-config",
        help="Generate marketplace.yaml from a CommonContext domain schema",
    )
    gen_parser.add_argument("--domain-schema", required=True, help="Path to <vertical>_schema.yaml")
    gen_parser.add_argument("-o", "--output", default="marketplace.yaml", help="Output path")
    gen_parser.add_argument("--name", help="Marketplace display name")
    gen_parser.add_argument("--industry", help="Industry label")
    gen_parser.add_argument("--enrich", action="store_true", help="Use OpenRouter LLM for repair")
    gen_parser.add_argument("--stdout", action="store_true", help="Print YAML instead of writing a file")
    gen_parser.add_argument("--provenance", action="store_true", help="Print field->source provenance map")

    args = parser.parse_args()

    if args.command == "generate-config":
        from configgen.cli import main as gen_main

        argv = ["--domain-schema", args.domain_schema, "-o", args.output]
        if args.name:
            argv += ["--name", args.name]
        if args.industry:
            argv += ["--industry", args.industry]
        if args.enrich:
            argv.append("--enrich")
        if args.stdout:
            argv.append("--stdout")
        if args.provenance:
            argv.append("--provenance")
        sys.exit(gen_main(argv))
    if args.command == "validate":
        from cli.validate import validate_config_file

        valid = validate_config_file(args.file)
        sys.exit(0 if valid else 1)
    if args.command == "compile":
        from cli.compile import run_compile

        ok = run_compile(
            config_path=args.config,
            mode=args.mode,
            export_enabled=bool(args.export),
            export_dir=args.export_dir,
            check=bool(args.check),
        )
        sys.exit(0 if ok else 1)
    if args.command == "export":
        from cli.compile import run_compile

        ok = run_compile(
            config_path=args.config,
            mode=args.mode,
            export_enabled=True,
            export_dir=args.export_dir,
            check=False,
        )
        sys.exit(0 if ok else 1)
    else:
        # Default to wizard (no subcommand or explicit "wizard")
        from cli.wizard import run_wizard

        output = getattr(args, "output", "marketplace.yaml") or "marketplace.yaml"
        preset = getattr(args, "preset", None)
        run_wizard(output_path=output, preset_name=preset)


if __name__ == "__main__":
    main()
