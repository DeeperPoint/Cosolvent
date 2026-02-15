from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.marketplace_config import (
    MarketplaceConfig,
    get_marketplace_config,
    load_marketplace_config,
    set_marketplace_config,
)

router = APIRouter()

_PANEL_HTML = (Path(__file__).with_name("panel.html")).read_text(encoding="utf-8")


class ConfigPayload(BaseModel):
    config: dict[str, Any]


class SavePayload(ConfigPayload):
    output_path: str | None = None
    apply_runtime: bool = True


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_panel() -> HTMLResponse:
    return HTMLResponse(_PANEL_HTML)


@router.get("/api/setup/config-template")
async def get_config_template() -> dict[str, Any]:
    runtime_path = _runtime_config_path()
    config, source_path, seeded_from_example = _current_config(runtime_path)
    return {
        "config": config.model_dump(),
        "source_path": str(source_path),
        "runtime_path": str(runtime_path),
        "seeded_from_example": seeded_from_example,
    }


@router.post("/api/setup/validate")
async def validate_config(payload: ConfigPayload) -> dict[str, Any]:
    config = _parse_config(payload.config)
    return {
        "valid": True,
        "config": config.model_dump(),
    }


@router.post("/api/setup/render-yaml")
async def render_yaml(payload: ConfigPayload) -> dict[str, Any]:
    config = _parse_config(payload.config)
    yaml_text = yaml.safe_dump(config.model_dump(), sort_keys=False, allow_unicode=False)
    return {"yaml": yaml_text}


@router.post("/api/setup/save")
async def save_config(payload: SavePayload) -> dict[str, Any]:
    config = _parse_config(payload.config)
    target_path = _resolve_output_path(payload.output_path)
    yaml_text = yaml.safe_dump(config.model_dump(), sort_keys=False, allow_unicode=False)
    target_path.write_text(yaml_text, encoding="utf-8")

    if payload.apply_runtime:
        set_marketplace_config(config)

    return {
        "saved": True,
        "path": str(target_path),
        "bytes": len(yaml_text.encode("utf-8")),
        "applied_runtime": payload.apply_runtime,
    }


def _current_config(runtime_path: Path) -> tuple[MarketplaceConfig, Path, bool]:
    try:
        return get_marketplace_config(), runtime_path, False
    except RuntimeError:
        source_path, seeded_from_example = _ensure_runtime_config(runtime_path)
        return load_marketplace_config(runtime_path), source_path, seeded_from_example


def _runtime_config_path() -> Path:
    requested = Path(settings.marketplace_config_path)
    return requested.resolve() if requested.is_absolute() else (Path.cwd() / requested).resolve()


def _example_config_path(runtime_path: Path) -> Path:
    if runtime_path.suffix.lower() in {".yaml", ".yml"}:
        return runtime_path.with_name(f"{runtime_path.stem}.example{runtime_path.suffix}")
    return runtime_path.with_name("marketplace.example.yaml")


def _ensure_runtime_config(runtime_path: Path) -> tuple[Path, bool]:
    if runtime_path.exists():
        if runtime_path.is_dir():
            raise HTTPException(
                status_code=500,
                detail=f"Runtime config path is a directory, expected a file: {runtime_path}",
            )
        return runtime_path, False

    example_path = _example_config_path(runtime_path)
    if not example_path.exists() or not example_path.is_file():
        raise HTTPException(
            status_code=500,
            detail=(
                f"Runtime config missing at {runtime_path} and example config "
                f"not found at {example_path}"
            ),
        )

    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    return example_path, True


def _parse_config(raw: dict[str, Any]) -> MarketplaceConfig:
    try:
        return MarketplaceConfig(**raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Config validation failed",
                "errors": exc.errors(),
            },
        ) from exc


def _resolve_output_path(output_path: str | None) -> Path:
    base = Path.cwd().resolve()
    if output_path and output_path.strip():
        requested = Path(output_path)
        target = requested.resolve() if requested.is_absolute() else (base / requested).resolve()
    else:
        target = _runtime_config_path()

    if target.suffix.lower() not in {".yaml", ".yml"}:
        raise HTTPException(status_code=400, detail="output_path must end in .yaml or .yml")

    if target != base and base not in target.parents:
        raise HTTPException(status_code=400, detail="output_path must stay within project directory")

    if target.exists() and target.is_dir():
        raise HTTPException(status_code=400, detail=f"output_path points to a directory: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)

    return target
