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

    # load-references subcommand — load a CommonContext reference export into the DB
    refs_parser = subparsers.add_parser(
        "load-references",
        help="Load a CommonContext reference-library JSONL export into reference_library",
    )
    refs_parser.add_argument("file", help="Path to the ingestion JSONL export")
    refs_parser.add_argument("--vertical", help="Default vertical if records omit it")

    pop_parser = subparsers.add_parser(
        "load-population",
        help="Load a C0 synthetic population file (watermark-enforced) into profiles",
    )
    pop_parser.add_argument("file", help="Path to the population JSON file")
    pop_parser.add_argument("--config", default=None, help="marketplace.yaml path (default: settings)")
    pop_parser.add_argument(
        "--mode", choices=["demo", "production"], default="demo",
        help="demo requires valid watermarks; production rejects watermarked records",
    )
    pop_parser.add_argument("--no-index", action="store_true", help="Skip embedding/indexing")

    stamp_parser = subparsers.add_parser(
        "stamp-population",
        help="Sign a raw population file with synthetic watermarks (reference signer)",
    )
    stamp_parser.add_argument("file", help="Path to the raw population JSON file")
    stamp_parser.add_argument("-o", "--output", required=True, help="Output (watermarked) file path")
    stamp_parser.add_argument("--secret", default=None, help="Override the watermark secret")

    args = parser.parse_args()

    if args.command == "load-references":
        from cli.load_references import load_references_file

        ok = load_references_file(args.file, args.vertical)
        sys.exit(0 if ok else 1)
    if args.command == "load-population":
        from app.core.config import settings
        from cli.load_population import load_population

        config_path = args.config or settings.marketplace_config_path
        ok = load_population(args.file, config_path, mode=args.mode, do_index=not args.no_index)
        sys.exit(0 if ok else 1)
    if args.command == "stamp-population":
        from cli.stamp_population import stamp_population

        ok = stamp_population(args.file, args.output, secret=args.secret)
        sys.exit(0 if ok else 1)
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
