"""Twin provisioning: sequencing, preflight and stage selection.

The stages themselves are the same functions their standalone commands call and
are covered by those commands' tests. What is new here — and what these cover —
is the orchestration: what runs, in what order, what is refused before anything
writes, and where a run stops.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from cli import provision
from cli.provision import ProvisionPlan, StageResult

CONFIG = "tests/test_config/agriculture.yaml"


def _plan(**kw) -> ProvisionPlan:
    return ProvisionPlan(config_path=CONFIG, **kw)


# -- Stage selection ------------------------------------------------------

class TestStageSelection:
    def test_all_stages_run_by_default(self):
        plan = _plan()
        assert all(plan.runs(s) for s in provision.STAGES)

    def test_only_restricts_to_named_stages(self):
        plan = _plan(only=("population",))
        assert plan.runs("population")
        assert not plan.runs("precompute")
        assert not plan.runs("preflight")

    def test_skip_excludes_named_stages(self):
        plan = _plan(skip=("precompute",))
        assert plan.runs("population")
        assert not plan.runs("precompute")

    def test_only_takes_precedence_over_skip(self):
        """Both given is a contradiction; --only is the more explicit instruction."""
        plan = _plan(only=("knowledge",), skip=("knowledge",))
        assert plan.runs("knowledge")

    def test_only_does_not_narrow_what_preflight_validates(self):
        """`--only preflight` is how an operator asks "would a full run succeed?".
        Gating the checks on execution scope made it validate *less* than a real
        run - the exact opposite of its purpose."""
        plan = _plan(only=("preflight",), population="p.json")
        assert not plan.runs("population")      # will not execute
        assert plan.validates("population")     # but is still checked

    def test_skip_does_narrow_what_preflight_validates(self):
        """Skipping a stage is a statement that its preconditions do not apply."""
        plan = _plan(skip=("population",), population="p.json")
        assert not plan.validates("population")

    def test_dry_run_describes_without_executing(self):
        lines = provision.describe_plan(_plan(population="p.json"))
        assert lines[0].startswith("would run: preflight -> configure")
        # Stages with no input are called out rather than silently no-oping.
        assert any("knowledge" in line and "skipped" in line for line in lines)


# -- Preflight ------------------------------------------------------------

class TestPreflight:
    async def test_rejects_an_unparseable_config(self):
        res = await provision.preflight(ProvisionPlan(config_path="does/not/exist.yaml"))
        assert res.status == "failed"
        assert "marketplace config" in res.detail

    async def test_rejects_a_missing_input_file(self):
        plan = _plan(population="no/such/population.json", index=False)
        res = await provision.preflight(plan)
        assert res.status == "failed"
        assert "population file not found" in res.detail

    async def test_rejects_a_placeholder_watermark_secret(self, monkeypatch, tmp_path):
        """A placeholder secret rejects every record at the boundary — catching it
        here costs milliseconds instead of a full load that admits nothing."""
        from app.core.config import settings

        pop = tmp_path / "population.json"
        pop.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(settings, "synthetic_watermark_secret", "change-me-synthetic")

        res = await provision.preflight(_plan(population=str(pop), index=False))
        assert res.status == "failed"
        assert "WATERMARK_SECRET" in res.detail

    async def test_accepts_a_real_watermark_secret(self, monkeypatch, tmp_path):
        from app.core.config import settings

        pop = tmp_path / "population.json"
        pop.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(settings, "synthetic_watermark_secret", "a-real-secret")

        res = await provision.preflight(_plan(population=str(pop), index=False))
        assert res.status == "ok"

    async def test_reports_the_marketplace_it_resolved(self):
        res = await provision.preflight(_plan(index=False, skip=("precompute",)))
        assert res.status == "ok"
        assert "GrainPlaza" in res.detail

    async def test_embedding_check_runs_when_indexing(self, monkeypatch, tmp_path):
        from app.core.config import settings

        pop = tmp_path / "population.json"
        pop.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(settings, "synthetic_watermark_secret", "a-real-secret")

        with patch.object(
            provision, "check_embedding_provider",
            new=AsyncMock(return_value=(False, "no API key")),
        ):
            res = await provision.preflight(_plan(population=str(pop), index=True))
        assert res.status == "failed"
        assert "no API key" in res.detail

    async def test_embedding_check_skipped_when_not_indexing(self, monkeypatch, tmp_path):
        from app.core.config import settings

        pop = tmp_path / "population.json"
        pop.write_text("[]", encoding="utf-8")
        monkeypatch.setattr(settings, "synthetic_watermark_secret", "a-real-secret")

        called = AsyncMock(return_value=(False, "should not be consulted"))
        with patch.object(provision, "check_embedding_provider", new=called):
            res = await provision.preflight(
                _plan(population=str(pop), index=False, skip=("precompute",))
            )
        assert res.status == "ok"
        called.assert_not_awaited()


class TestEmbeddingProviderCheck:
    async def test_rejects_an_unkeyed_provider(self, monkeypatch):
        """The failure this command exists to prevent: records load, nothing indexes."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", "", raising=False)
        with patch(
            "app.modules.ai.repository.get_embedding_config",
            new=AsyncMock(return_value={"provider": "openai", "model": "m", "dimensions": 1536}),
        ):
            ok, detail = await provision.check_embedding_provider()
        assert ok is False
        assert "no API key" in detail

    async def test_rejects_a_dimension_mismatch(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "gemini_api_key", "key", raising=False)
        with patch(
            "app.modules.ai.repository.get_embedding_config",
            new=AsyncMock(return_value={"provider": "gemini", "model": "m", "dimensions": 768}),
        ):
            ok, detail = await provision.check_embedding_provider()
        assert ok is False
        assert "768" in detail

    async def test_accepts_a_keyed_compatible_provider(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openrouter_api_key", "key", raising=False)
        with patch(
            "app.modules.ai.repository.get_embedding_config",
            new=AsyncMock(return_value={"provider": "openrouter", "model": "m", "dimensions": 1536}),
        ):
            ok, detail = await provision.check_embedding_provider()
        assert ok is True
        assert "openrouter" in detail

    async def test_rejects_an_unregistered_provider(self):
        with patch(
            "app.modules.ai.repository.get_embedding_config",
            new=AsyncMock(return_value={"provider": "nonesuch", "model": "m", "dimensions": 1536}),
        ):
            ok, detail = await provision.check_embedding_provider()
        assert ok is False
        assert "registry" in detail


# -- Stages that are skipped without input --------------------------------

class TestSkippedStages:
    async def test_knowledge_skipped_without_references(self):
        res = await provision.knowledge(_plan())
        assert res.status == "skipped"

    async def test_population_skipped_without_a_file(self):
        res = await provision.population(_plan())
        assert res.status == "skipped"

    def test_contract_skipped_without_a_schema_dir(self):
        res = provision.contract(_plan())
        assert res.status == "skipped"


# -- Precompute guard -----------------------------------------------------

class TestPrecomputeGuard:
    async def test_refuses_to_cache_a_partial_market(self):
        """A cache built over a partially loaded population presents as deliberate
        rather than broken, which is worse than an obvious failure."""
        pop = StageResult("population", "ok", "", {"loaded": 4, "rejected": 2})
        res = await provision.precompute(_plan(), pop)
        assert res.status == "failed"
        assert "--allow-partial" in res.detail

    async def test_refuses_when_records_loaded_but_did_not_index(self):
        """Observed live: a transient provider error left 1 of 6 records unindexed.
        Those records are in the database and invisible to search, so a cache built
        over them presents a market missing a participant."""
        pop = StageResult("population", "ok", "", {"loaded": 6, "rejected": 0, "unindexed": 1})
        res = await provision.precompute(_plan(), pop)
        assert res.status == "failed"
        assert "not indexed" in res.detail

    async def test_reports_both_kinds_of_incompleteness(self):
        pop = StageResult("population", "ok", "", {"loaded": 4, "rejected": 2, "unindexed": 1})
        res = await provision.precompute(_plan(), pop)
        assert res.status == "failed"
        assert "2 rejected" in res.detail and "1 loaded but not indexed" in res.detail

    async def test_allow_partial_overrides_the_guard(self):
        pop = StageResult("population", "ok", "", {"loaded": 4, "rejected": 2})
        with patch(
            "app.modules.showcase.run_precompute",
            new=AsyncMock(return_value=type("R", (), {
                "personas_cached": 4, "matches_cached": 2, "qa_cached": 1, "errors": [],
            })()),
        ):
            res = await provision.precompute(_plan(allow_partial=True), pop)
        assert res.status == "ok"

    async def test_runs_when_nothing_was_rejected(self):
        pop = StageResult("population", "ok", "", {"loaded": 6, "rejected": 0})
        with patch(
            "app.modules.showcase.run_precompute",
            new=AsyncMock(return_value=type("R", (), {
                "personas_cached": 6, "matches_cached": 3, "qa_cached": 2, "errors": [],
            })()),
        ):
            res = await provision.precompute(_plan(), pop)
        assert res.status == "ok"
        assert res.data["personas"] == 6


# -- Sequencing -----------------------------------------------------------

class TestSequencing:
    async def test_stops_at_the_first_failure(self, monkeypatch):
        """A stage that fails must not be followed by one that assumes it worked."""
        monkeypatch.setattr(provision, "preflight", AsyncMock(
            return_value=StageResult("preflight", "ok", "")))
        monkeypatch.setattr(provision, "configure", lambda plan: StageResult(
            "configure", "failed", "boom"))
        should_not_run = AsyncMock()
        monkeypatch.setattr(provision, "knowledge", should_not_run)

        with patch("app.core.database.connect_db", new=AsyncMock()), \
             patch("app.core.database.close_db", new=AsyncMock()):
            results = await provision.run_stages(_plan())

        assert [r.name for r in results] == ["preflight", "configure"]
        should_not_run.assert_not_awaited()

    async def test_a_failed_preflight_writes_nothing(self, monkeypatch):
        monkeypatch.setattr(provision, "preflight", AsyncMock(
            return_value=StageResult("preflight", "failed", "bad config")))
        never = AsyncMock()
        monkeypatch.setattr(provision, "knowledge", never)

        with patch("app.core.database.connect_db", new=AsyncMock()), \
             patch("app.core.database.close_db", new=AsyncMock()):
            results = await provision.run_stages(_plan())

        assert len(results) == 1 and results[0].status == "failed"
        never.assert_not_awaited()

    async def test_unreachable_database_is_reported_as_preflight(self):
        with patch("app.core.database.connect_db", new=AsyncMock(side_effect=OSError("refused"))):
            results = await provision.run_stages(_plan())
        assert len(results) == 1
        assert results[0].name == "preflight" and results[0].status == "failed"
        assert "database unreachable" in results[0].detail

    async def test_stages_run_in_the_declared_order(self, monkeypatch):
        """Ordering is load-bearing: contract before population, population before precompute."""
        seen: list[str] = []

        monkeypatch.setattr(provision, "preflight", AsyncMock(
            return_value=StageResult("preflight", "ok", "")))
        monkeypatch.setattr(provision, "configure",
                            lambda p: (seen.append("configure"), StageResult("configure", "ok"))[1])
        for name in ("knowledge", "population"):
            monkeypatch.setattr(
                provision, name,
                AsyncMock(side_effect=lambda p, n=name: (seen.append(n), StageResult(n, "ok"))[1]),
            )
        monkeypatch.setattr(provision, "contract",
                            lambda p: (seen.append("contract"), StageResult("contract", "ok"))[1])
        monkeypatch.setattr(
            provision, "precompute",
            AsyncMock(side_effect=lambda p, pop: (seen.append("precompute"), StageResult("precompute", "ok"))[1]),
        )

        with patch("app.core.database.connect_db", new=AsyncMock()), \
             patch("app.core.database.close_db", new=AsyncMock()):
            await provision.run_stages(_plan())

        assert seen == ["configure", "knowledge", "contract", "population", "precompute"]

    async def test_a_raising_stage_is_reported_not_propagated(self, monkeypatch):
        """An operator needs to know which step broke and that nothing after it
        ran. A stack trace buries both, so the exception becomes a failed stage."""
        monkeypatch.setattr(provision, "preflight", AsyncMock(
            return_value=StageResult("preflight", "ok", "")))
        monkeypatch.setattr(provision, "configure",
                            lambda p: (_ for _ in ()).throw(RuntimeError("kaboom")))
        never = AsyncMock()
        monkeypatch.setattr(provision, "knowledge", never)
        closed = AsyncMock()

        with patch("app.core.database.connect_db", new=AsyncMock()), \
             patch("app.core.database.close_db", new=closed):
            results = await provision.run_stages(_plan())

        assert [r.name for r in results] == ["preflight", "configure"]
        assert results[-1].status == "failed"
        assert "RuntimeError: kaboom" in results[-1].detail
        never.assert_not_awaited()
        # The connection is still released on the failure path.
        closed.assert_awaited()
