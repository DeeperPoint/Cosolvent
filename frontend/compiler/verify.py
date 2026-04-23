"""Build/type verification helpers for generated frontend artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    summary: str


def run_frontend_verification(output_dir: Path, artifacts: dict[str, str]) -> VerificationResult:
    """Run `npm run type-check` and `npm run build` in an isolated temp dir."""
    output_dir = output_dir.resolve()

    with tempfile.TemporaryDirectory(prefix="frontend-verify-") as tmp:
        tmpdir = Path(tmp)
        _seed_from_existing_output(output_dir, tmpdir)
        _write_artifacts(tmpdir, artifacts)

        package_json = tmpdir / "package.json"
        if not package_json.exists():
            return VerificationResult(False, "Verification failed: package.json missing in artifacts")

        if not (tmpdir / "node_modules").exists():
            install_res = _run_command(["npm", "install"], tmpdir)
            if install_res.returncode != 0:
                return VerificationResult(
                    False,
                    f"npm install failed:\n{_truncate((install_res.stdout or '') + (install_res.stderr or ''))}",
                )

        typecheck_res = _run_command(["npm", "run", "type-check"], tmpdir)
        if typecheck_res.returncode != 0:
            return VerificationResult(
                False,
                f"type-check failed:\n{_truncate((typecheck_res.stdout or '') + (typecheck_res.stderr or ''))}",
            )

        build_res = _run_command(["npm", "run", "build"], tmpdir)
        if build_res.returncode != 0:
            return VerificationResult(
                False,
                f"build failed:\n{_truncate((build_res.stdout or '') + (build_res.stderr or ''))}",
            )

        return VerificationResult(True, "verification passed")


def _seed_from_existing_output(source_dir: Path, target_dir: Path) -> None:
    """Copy only minimal runtime dirs if they already exist (e.g., node_modules)."""
    maybe_copy = ("node_modules",)
    for rel in maybe_copy:
        src = source_dir / rel
        dst = target_dir / rel
        if src.exists() and src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)


def _write_artifacts(target_dir: Path, artifacts: dict[str, str]) -> None:
    for rel, content in artifacts.items():
        path = target_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _run_command(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...<truncated>..."
