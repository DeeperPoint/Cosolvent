"""The compiler must never delete an Alembic migration it previously generated.

Generated code under `app/generated/` is a projection of the current config, so
pruning it when the config changes is correct. A migration is not a projection: it
may already have been applied to a database, and it stays referenced by the
revision chain.

Before this was separated, compiling a second marketplace config deleted the first
one's migration from the working tree — a file that is normally committed — so the
developer saw a deletion in `git status` that they had not made. Committing with
`-a` would have removed real schema history.
"""

from __future__ import annotations

import json

import pytest

from app.compiler import manifest as m
from app.compiler.writer import write_artifacts

MIGRATION_A = "alembic/versions/auto_marketplace_mkt_aaaaaaaaaaaa.py"
MIGRATION_B = "alembic/versions/auto_marketplace_mkt_bbbbbbbbbbbb.py"
GENERATED_CODE = "app/generated/enums.py"


class TestPrunablePaths:
    def test_generated_code_is_prunable(self):
        assert m.is_prunable_path(GENERATED_CODE) is True

    def test_openapi_is_prunable(self):
        assert m.is_prunable_path("openapi/generated_openapi.json") is True

    def test_migrations_are_not_prunable(self):
        assert m.is_prunable_path(MIGRATION_A) is False

    def test_migrations_are_still_managed(self):
        """They remain compiler-owned and manifest-tracked — just never deleted."""
        assert m.is_managed_path(MIGRATION_A) is True

    def test_unrelated_paths_are_neither(self):
        assert m.is_managed_path("app/modules/auth/service.py") is False
        assert m.is_prunable_path("app/modules/auth/service.py") is False


class TestStaleDetection:
    @pytest.fixture
    def root_with_manifest(self, tmp_path):
        (tmp_path / "generated").mkdir(parents=True)
        (tmp_path / "generated" / "manifest.json").write_text(
            json.dumps({"generated_files": [MIGRATION_A, GENERATED_CODE]}),
            encoding="utf-8",
        )
        return tmp_path

    def test_previous_migration_is_not_reported_stale(self, root_with_manifest):
        """The core guarantee: compiling config B leaves config A's migration alone."""
        stale = m.stale_managed_files(root_with_manifest, {MIGRATION_B})
        assert MIGRATION_A not in stale

    def test_superseded_generated_code_is_reported_stale(self, root_with_manifest):
        stale = m.stale_managed_files(root_with_manifest, {MIGRATION_B})
        assert GENERATED_CODE in stale

    def test_regenerated_files_are_never_stale(self, root_with_manifest):
        stale = m.stale_managed_files(root_with_manifest, {MIGRATION_A, GENERATED_CODE})
        assert stale == []


class TestWriteArtifactsDoesNotDeleteMigrations:
    def test_compiling_a_different_config_keeps_the_earlier_migration(self, tmp_path):
        """End-to-end through the writer, which is what actually unlinks files."""
        (tmp_path / "alembic" / "versions").mkdir(parents=True)
        (tmp_path / "app" / "generated").mkdir(parents=True)
        (tmp_path / "generated").mkdir(parents=True)

        migration_a = tmp_path / MIGRATION_A
        migration_a.write_text("# committed schema history\n", encoding="utf-8")
        (tmp_path / GENERATED_CODE).write_text("# old projection\n", encoding="utf-8")
        (tmp_path / "generated" / "manifest.json").write_text(
            json.dumps({"generated_files": [MIGRATION_A, GENERATED_CODE]}),
            encoding="utf-8",
        )

        # Compile a different config: it emits migration B and fresh generated code.
        _generated, removed = write_artifacts(
            tmp_path,
            {MIGRATION_B: "# new migration\n", GENERATED_CODE: "# new projection\n"},
            keep_paths={"generated/manifest.json"},
        )

        assert migration_a.exists(), "a previously generated migration must survive"
        assert MIGRATION_A not in removed
        assert (tmp_path / MIGRATION_B).exists()
