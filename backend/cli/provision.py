"""CLI: stand up a digital twin end to end.

    python -m cli provision-twin --config marketplace.yaml \
        --references knowledge/export.jsonl \
        --population population.json \
        --schema-dir contracts/

Provisioning is a fixed sequence whose order is load-bearing: a profile schema
must be published before a generator can conform to it, records must load before
they can be indexed, and the showcase cache must be baked last or it caches an
empty market. That order previously lived only in an operator's memory, spread
across ten separate commands.

Each stage delegates to the same function its standalone command calls, so this
adds sequencing, preflight and reporting - not a second implementation of any
step. Stages whose inputs are absent are skipped, so a partial provision (say,
reloading the population only) is the same command with fewer arguments.

Note the boundary: this *loads* a population file, it does not generate one.
Generation belongs to ClientSynth, which reads the contract published by the
`contract` stage.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STAGES = ("preflight", "configure", "knowledge", "contract", "population", "precompute")

# The pgvector columns are fixed at this width; a provider emitting anything else
# is rejected on every insert rather than at configuration time.
REQUIRED_EMBEDDING_DIMENSIONS = 1536

# Shipped placeholders. Provisioning with either means the watermark cannot be
# verified against whatever signed the population.
PLACEHOLDER_SECRETS = {"", "change-me-synthetic", "change-me"}


@dataclass
class StageResult:
    name: str
    status: str  # "ok" | "skipped" | "failed"
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvisionPlan:
    config_path: str
    domain_schema: str | None = None
    references: str | None = None
    population: str | None = None
    schema_dir: str | None = None
    mode: str = "demo"
    index: bool = True
    allow_partial: bool = False
    only: tuple[str, ...] = ()
    skip: tuple[str, ...] = ()

    def runs(self, stage: str) -> bool:
        """Whether this invocation will execute `stage`."""
        if self.only:
            return stage in self.only
        return stage not in self.skip

    def validates(self, stage: str) -> bool:
        """Whether preflight should check the preconditions for `stage`.

        Deliberately ignores `--only`: `--only preflight` is how an operator asks
        "would a full run succeed?", so narrowing execution must not narrow what
        gets validated. `--skip` is respected, because skipping a stage is a
        statement that its preconditions do not apply.
        """
        return stage not in self.skip


# -- Preflight -----------------------------------------------------------

async def check_embedding_provider() -> tuple[bool, str]:
    """An unkeyed provider is the failure this whole command exists to prevent:
    the population loads, every index call raises, and the records sit in the
    database undiscoverable while the run reports success."""
    from app.core.config import settings
    from app.modules.ai.providers import PROVIDER_REGISTRY
    from app.modules.ai.repository import get_embedding_config

    cfg = await get_embedding_config()
    provider, dims = cfg["provider"], cfg["dimensions"]

    spec = next(
        (sp for pid, sp in PROVIDER_REGISTRY.items() if str(getattr(pid, "value", pid)) == provider),
        None,
    )
    if spec is None:
        return False, f"embedding provider {provider!r} is not in the registry"
    if not getattr(settings, spec.api_key_env_name, ""):
        return False, (
            f"embedding provider {provider!r} has no API key "
            f"({spec.api_key_env_name.upper()} is empty) - the population would load but index nothing"
        )
    if dims != REQUIRED_EMBEDDING_DIMENSIONS:
        return False, (
            f"embedding dimensions {dims} do not match the pgvector column "
            f"({REQUIRED_EMBEDDING_DIMENSIONS}) - every insert would be rejected"
        )
    return True, f"{provider} @ {dims}d"


async def preflight(plan: ProvisionPlan) -> StageResult:
    """Validate everything cheap before anything writes."""
    from app.core.config import settings
    from app.core.marketplace_config import load_marketplace_config

    problems: list[str] = []
    notes: list[str] = []

    # 1. Marketplace config parses.
    try:
        config = load_marketplace_config(plan.config_path)
        notes.append(f"config {config.marketplace.name!r} ({len(config.participant_types)} types)")
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return StageResult("preflight", "failed", f"marketplace config: {exc}")

    # 2. Named input files exist, before any of them is half-consumed.
    for label, path in (
        ("references", plan.references),
        ("population", plan.population),
        ("domain schema", plan.domain_schema),
    ):
        if path and not Path(path).exists():
            problems.append(f"{label} file not found: {path}")

    # 3. Indexing needs a usable embedding provider.
    needs_embeddings = plan.index and (
        (plan.validates("population") and bool(plan.population)) or plan.validates("precompute")
    )
    if needs_embeddings:
        ok, detail = await check_embedding_provider()
        (notes if ok else problems).append(f"embeddings: {detail}")

    # 4. A population cannot be verified against a placeholder secret.
    if plan.population and plan.validates("population") and plan.mode == "demo":
        if settings.synthetic_watermark_secret in PLACEHOLDER_SECRETS:
            problems.append(
                "SYNTHETIC_WATERMARK_SECRET is unset or still the shipped placeholder - "
                "every record would be rejected at the ingest boundary"
            )

    if problems:
        return StageResult("preflight", "failed", "; ".join(problems))
    return StageResult("preflight", "ok", "; ".join(notes))


# -- Stages --------------------------------------------------------------

def configure(plan: ProvisionPlan) -> StageResult:
    from cli.compile import run_compile

    if not plan.domain_schema:
        # Compiling an existing config is still worth doing: it regenerates the
        # runtime artefacts the rest of the run depends on.
        ok = run_compile(
            config_path=plan.config_path, mode="mvp", export_enabled=False,
            export_dir="exports", check=False,
        )
        return StageResult("configure", "ok" if ok else "failed", "compiled existing config")

    from configgen.cli import main as generate_config

    rc = generate_config(["--domain-schema", plan.domain_schema, "-o", plan.config_path])
    if rc != 0:
        return StageResult("configure", "failed", f"generate-config exited {rc}")
    ok = run_compile(
        config_path=plan.config_path, mode="mvp", export_enabled=False,
        export_dir="exports", check=False,
    )
    return StageResult(
        "configure", "ok" if ok else "failed",
        f"generated from {plan.domain_schema} and compiled",
    )


async def knowledge(plan: ProvisionPlan) -> StageResult:
    if not plan.references:
        return StageResult("knowledge", "skipped", "no --references given")

    from app.modules.knowledge.service import load_reference_records
    from cli.load_references import _read_jsonl

    records = _read_jsonl(Path(plan.references))
    if not records:
        return StageResult("knowledge", "failed", f"no records in {plan.references}")
    result = await load_reference_records(records)
    return StageResult("knowledge", "ok", f"loaded {result['loaded']} chunk(s)", dict(result))


def contract(plan: ProvisionPlan) -> StageResult:
    if not plan.schema_dir:
        return StageResult("contract", "skipped", "no --schema-dir given")

    from app.core.marketplace_config import load_marketplace_config
    from cli.export_profile_schema import export_profile_schema

    config = load_marketplace_config(plan.config_path)
    out_dir = Path(plan.schema_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for pt in config.profile_schemas:
        path = out_dir / f"{pt}.schema.json"
        if not export_profile_schema(pt, plan.config_path, str(path)):
            return StageResult("contract", "failed", f"could not publish schema for {pt!r}")
        written.append(pt)
    return StageResult(
        "contract", "ok",
        f"published {len(written)} schema(s): {', '.join(written)}",
        {"participant_types": written},
    )


async def population(plan: ProvisionPlan) -> StageResult:
    if not plan.population:
        return StageResult("population", "skipped", "no --population given")

    from app.core.marketplace_config import load_marketplace_config
    from app.modules.population.loader import load_population_file
    from app.modules.population.service import import_population

    config = load_marketplace_config(plan.config_path)
    records = load_population_file(plan.population)
    res = await import_population(config, records, mode=plan.mode, do_index=plan.index)

    rejected = res.rejected_watermark + res.skipped_invalid
    detail = (
        f"loaded={res.loaded} updated={res.updated} indexed={res.indexed} "
        f"rejected_watermark={res.rejected_watermark} skipped_invalid={res.skipped_invalid}"
    )
    admitted = res.loaded + res.updated
    data = {
        "loaded": res.loaded, "updated": res.updated, "indexed": res.indexed,
        "rejected": rejected,
        # A record that loaded but did not index is in the database and invisible
        # to search. Indexing is best-effort per record inside the importer, so
        # this shortfall is reported rather than raised there - the guard below
        # is what stops a cache being baked over it.
        "unindexed": (admitted - res.indexed) if plan.index else 0,
        "errors": res.errors[:10],
    }

    if res.loaded + res.updated == 0:
        return StageResult("population", "failed", f"no records admitted - {detail}", data)
    return StageResult("population", "ok", detail, data)


async def precompute(plan: ProvisionPlan, population_result: StageResult | None) -> StageResult:
    """Bake the Mode-1 cache.

    Refuses to run over an incomplete population unless explicitly allowed: a
    cache built from a partially loaded market presents as deliberate rather
    than broken, which is worse than an obvious failure.
    """
    if population_result and not plan.allow_partial:
        rejected = population_result.data.get("rejected") or 0
        unindexed = population_result.data.get("unindexed") or 0
        if rejected or unindexed:
            reasons = []
            if rejected:
                reasons.append(f"{rejected} rejected")
            if unindexed:
                # Observed live: a transient provider error left 1 of 6 records
                # unindexed. Caching over that yields a market missing a
                # participant, which reads as a design choice rather than a fault.
                reasons.append(f"{unindexed} loaded but not indexed")
            return StageResult(
                "precompute", "failed",
                f"population incomplete ({', '.join(reasons)}) - refusing to cache a partial "
                "market (pass --allow-partial to override)",
            )

    from app.core.marketplace_config import load_marketplace_config
    from app.modules.showcase import run_precompute

    config = load_marketplace_config(plan.config_path)
    result = await run_precompute(config)
    detail = f"personas={result.personas_cached} matches={result.matches_cached} qa={result.qa_cached}"
    data = {
        "personas": result.personas_cached, "matches": result.matches_cached,
        "qa": result.qa_cached, "errors": result.errors[:10],
    }
    if result.errors and not result.personas_cached:
        return StageResult("precompute", "failed", f"{detail}; {result.errors[0]}", data)
    return StageResult("precompute", "ok", detail, data)


# -- Runner --------------------------------------------------------------

async def run_stages(plan: ProvisionPlan) -> list[StageResult]:
    from app.core.database import close_db, connect_db

    results: list[StageResult] = []

    # Preflight reads embedding settings from the database, so the connection is
    # opened first and its failure is reported as preflight's rather than as an
    # unhandled error part-way through a stage.
    try:
        await connect_db()
    except Exception as exc:  # noqa: BLE001
        return [StageResult("preflight", "failed", f"database unreachable: {exc}")]

    population_result: StageResult | None = None
    try:
        if plan.runs("preflight"):
            pre = await preflight(plan)
            results.append(pre)
            if pre.status == "failed":
                return results
        else:
            results.append(StageResult("preflight", "skipped", "excluded by --only/--skip"))

        for stage in ("configure", "knowledge", "contract", "population", "precompute"):
            if not plan.runs(stage):
                results.append(StageResult(stage, "skipped", "excluded by --only/--skip"))
                continue

            # A stage that raises is a failed stage, not a traceback: the operator
            # needs to know which step broke and that nothing after it ran, which a
            # stack trace buries. The exception text is kept as the detail.
            try:
                if stage == "configure":
                    res = configure(plan)
                elif stage == "knowledge":
                    res = await knowledge(plan)
                elif stage == "contract":
                    res = contract(plan)
                elif stage == "population":
                    res = await population(plan)
                    population_result = res
                else:
                    res = await precompute(plan, population_result)
            except Exception as exc:  # noqa: BLE001 - reported per stage, not swallowed
                res = StageResult(stage, "failed", f"{type(exc).__name__}: {exc}")

            results.append(res)
            if res.status == "failed":
                break
    finally:
        await close_db()

    return results


def render(results: list[StageResult], as_json: bool) -> None:
    if as_json:
        print(json.dumps(
            [{"stage": r.name, "status": r.status, "detail": r.detail, **r.data} for r in results],
            indent=2, default=str,
        ))
        return
    symbols = {"ok": "[ok]", "skipped": "[--]", "failed": "[FAIL]"}
    for r in results:
        print(f"{symbols.get(r.status, '[?]'):>7} {r.name:<11} {r.detail}")


def describe_plan(plan: ProvisionPlan) -> list[str]:
    """The stages a run would execute, and which would no-op for lack of input."""
    lines = ["would run: " + " -> ".join(s for s in STAGES if plan.runs(s))]
    for stage, path in (
        ("configure", plan.domain_schema), ("knowledge", plan.references),
        ("contract", plan.schema_dir), ("population", plan.population),
    ):
        if plan.runs(stage) and not path:
            note = "would compile the existing config" if stage == "configure" else "no input given - would be skipped"
            lines.append(f"  {stage}: {note}")
    return lines


def provision_twin(plan: ProvisionPlan, as_json: bool = False, dry_run: bool = False) -> bool:
    if dry_run:
        for line in describe_plan(plan):
            print(line)
        return True

    results = asyncio.run(run_stages(plan))
    render(results, as_json)

    failed = [r for r in results if r.status == "failed"]
    if failed:
        print(f"[fail] provisioning stopped at {failed[0].name!r}")
        return False
    print("[ok] twin provisioned")
    return True
