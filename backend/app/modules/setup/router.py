from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ValidationError

from app.compiler import CompileOptions, check_compile_sync, compile_marketplace
from app.core.config import settings
from app.core.marketplace_config import (
    MarketplaceConfig,
    get_marketplace_config,
    load_marketplace_config,
    set_marketplace_config,
)
from app.modules.setup.presets import list_presets

router = APIRouter()

_SETUP_DIR = Path(__file__).parent
_PANEL_HTML = (_SETUP_DIR / "panel_v3.html").read_text(encoding="utf-8")
_ASSET_DIR = _SETUP_DIR / "ui"
_ALLOWED_ASSETS = {
    "main.js",
    "tokens.js",
    "help-content.js",
    "steps.js",
    "validation-mapper.js",
    "diff-renderer.js",
    "state-utils.js",
    "onboarding-v2.css",
    "onboarding-v3.css",
}


class ConfigPayload(BaseModel):
    config: dict[str, Any]


class SavePayload(ConfigPayload):
    output_path: str | None = None
    apply_runtime: bool = True


class GeneratePayload(BaseModel):
    config: dict[str, Any] | None = None
    mode: Literal["mvp", "strict"] = "mvp"
    export_enabled: bool = True
    export_dir: str = "exports"
    overwrite_policy: Literal["managed"] = "managed"


class GenerateCheckPayload(BaseModel):
    config: dict[str, Any] | None = None
    mode: Literal["mvp", "strict"] = "mvp"
    overwrite_policy: Literal["managed"] = "managed"


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_panel() -> HTMLResponse:
    return HTMLResponse(_PANEL_HTML)


@router.get(
    "/api/setup/assets/{asset_name}",
    response_class=FileResponse,
    responses={
        200: {
            "description": "Static asset",
            "content": {
                "application/javascript": {},
                "text/css": {},
                "text/plain": {},
            },
        },
        404: {"description": "Unknown or missing asset"},
    },
)
async def setup_asset(asset_name: str) -> FileResponse:
    if asset_name not in _ALLOWED_ASSETS:
        raise HTTPException(status_code=404, detail="Unknown setup asset")
    path = (_ASSET_DIR / asset_name).resolve()
    if _ASSET_DIR.resolve() not in path.parents:
        raise HTTPException(status_code=404, detail="Unknown setup asset")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Setup asset missing")
    media_type = "text/plain; charset=utf-8"
    if asset_name.endswith(".js"):
        media_type = "application/javascript; charset=utf-8"
    elif asset_name.endswith(".css"):
        media_type = "text/css; charset=utf-8"
    return FileResponse(path, media_type=media_type)


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


@router.get("/api/setup/presets")
async def get_setup_presets() -> dict[str, Any]:
    return {"presets": list_presets()}


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


@router.post("/api/setup/generate")
async def generate_project(payload: GeneratePayload) -> dict[str, Any]:
    try:
        config = _resolve_generate_config(payload.config)
        result = compile_marketplace(
            config=config,
            options=CompileOptions(
                mode=payload.mode,
                export_enabled=payload.export_enabled,
                export_dir=payload.export_dir,
                overwrite_policy=payload.overwrite_policy,
            ),
            project_root=Path.cwd(),
        )
        return result
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "Config validation failed", "errors": exc.errors()},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/setup/generate/check")
async def check_generated_sync(payload: GenerateCheckPayload) -> dict[str, Any]:
    try:
        config = _resolve_generate_config(payload.config)
        return check_compile_sync(
            config=config,
            options=CompileOptions(
                mode=payload.mode,
                export_enabled=False,
                overwrite_policy=payload.overwrite_policy,
            ),
            project_root=Path.cwd(),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "Config validation failed", "errors": exc.errors()},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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


def _resolve_generate_config(raw: dict[str, Any] | None) -> MarketplaceConfig:
    if raw is not None:
        return _parse_config(raw)
    runtime_path = _runtime_config_path()
    config, _, _ = _current_config(runtime_path)
    return config


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
