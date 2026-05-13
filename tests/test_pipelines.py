"""
Unit tests for the Pipelines backend — models, service logic, and API endpoints.
No real Databricks connection: all DB calls and SDK calls are mocked.
"""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Stub databricks.sdk before any backend import touches it
# ---------------------------------------------------------------------------
import sys, types

_sdk = types.ModuleType("databricks.sdk")
_sdk.WorkspaceClient = MagicMock
sys.modules.setdefault("databricks", types.ModuleType("databricks"))
sys.modules["databricks.sdk"] = _sdk
sys.modules.setdefault("databricks.sql", types.ModuleType("databricks.sql"))

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from backend.models.pipeline import (
    GoogleDorkingConfig,
    GoogleDorkingResult,
    PipelineRun,
    PipelineRunCreate,
    PipelineResultsPage,
    PipelineRunsPage,
)


# ===========================================================================
# Model tests — no I/O
# ===========================================================================
class TestGoogleDorkingConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = GoogleDorkingConfig(keywords=["leaked"])
        self.assertEqual(cfg.timeframe, 30)
        self.assertEqual(cfg.num_of_results, 100)
        self.assertTrue(cfg.verbatim)
        self.assertEqual(cfg.sites, [])
        self.assertEqual(cfg.clients, [])
        self.assertEqual(cfg.rule_out, [])

    def test_full_config(self):
        cfg = GoogleDorkingConfig(
            keywords=["kw1", "kw2"],
            sites=["t.me"],
            clients=["ActiveFence"],
            rule_out=["news"],
            timeframe=7,
            num_of_results=50,
            verbatim=False,
        )
        self.assertEqual(cfg.keywords, ["kw1", "kw2"])
        self.assertEqual(cfg.timeframe, 7)
        self.assertFalse(cfg.verbatim)

    def test_invalid_timeframe_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            GoogleDorkingConfig(keywords=["x"], timeframe=999)

    def test_pipeline_run_create_requires_team(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            PipelineRunCreate(pipeline_type="google_dorking", config=GoogleDorkingConfig(keywords=["x"]))


# ===========================================================================
# Service tests — DB calls mocked
# ===========================================================================
class TestPipelineService(unittest.TestCase):
    def _make_run_df(self, **overrides):
        row = {
            "id": "run-uuid-1",
            "team": "Child Safety",
            "pipeline_type": "google_dorking",
            "config_json": json.dumps({"keywords": ["leaked"], "timeframe": 30}),
            "status": "completed",
            "databricks_run_id": 12345,
            "row_count": 10,
            "created_at": datetime(2026, 5, 12, 10, 0, tzinfo=timezone.utc),
            "created_by": "nikital@activefence.com",
            "completed_at": datetime(2026, 5, 12, 10, 5, tzinfo=timezone.utc),
        }
        row.update(overrides)
        return pd.DataFrame([row])

    @patch("backend.services.pipeline.run_query")
    def test_get_pipeline_runs_returns_page(self, mock_query):
        count_df = pd.DataFrame([{"total": 1}])
        runs_df = self._make_run_df()
        mock_query.side_effect = [count_df, runs_df]

        from backend.services.pipeline import get_pipeline_runs
        page = get_pipeline_runs("Child Safety")

        self.assertEqual(page.total, 1)
        self.assertEqual(len(page.items), 1)
        self.assertEqual(page.items[0].id, "run-uuid-1")
        self.assertEqual(page.items[0].status, "completed")

    @patch("backend.services.pipeline.run_query")
    def test_get_pipeline_run_returns_none_for_missing(self, mock_query):
        mock_query.return_value = pd.DataFrame()

        from backend.services.pipeline import get_pipeline_run
        result = get_pipeline_run("nonexistent-id")
        self.assertIsNone(result)

    @patch("backend.services.pipeline.run_query")
    def test_get_pipeline_run_found(self, mock_query):
        mock_query.return_value = self._make_run_df()

        from backend.services.pipeline import get_pipeline_run
        run = get_pipeline_run("run-uuid-1")
        self.assertIsNotNone(run)
        self.assertEqual(run.team, "Child Safety")
        self.assertEqual(run.pipeline_type, "google_dorking")

    @patch("backend.services.pipeline.run_statement")
    def test_create_pipeline_run_inserts_row(self, mock_stmt):
        from backend.services.pipeline import create_pipeline_run
        cfg = GoogleDorkingConfig(keywords=["test"])
        run = create_pipeline_run("Child Safety", "google_dorking", cfg, "nikital@activefence.com")

        mock_stmt.assert_called_once()
        sql = mock_stmt.call_args[0][0]
        self.assertIn("INSERT INTO", sql)
        self.assertIn("pipeline_runs", sql)
        self.assertIn("pending", sql)

        self.assertEqual(run.status, "pending")
        self.assertEqual(run.team, "Child Safety")
        self.assertIsNotNone(run.id)

    @patch("backend.services.pipeline.run_statement")
    @patch("backend.services.pipeline.WorkspaceClient")
    def test_trigger_job_calls_run_now(self, mock_wc_class, mock_stmt):
        mock_wc = MagicMock()
        mock_wc.jobs.run_now.return_value = MagicMock(run_id=99999)
        mock_wc_class.return_value = mock_wc

        from backend.services.pipeline import trigger_google_dorking_job
        cfg = GoogleDorkingConfig(keywords=["kw1", "kw2"], sites=["t.me"], timeframe=7)
        run_id = trigger_google_dorking_job("run-uuid-1", "Child Safety", cfg)

        mock_wc.jobs.run_now.assert_called_once()
        call_kwargs = mock_wc.jobs.run_now.call_args[1]
        params = call_kwargs["notebook_params"]

        self.assertEqual(params["keywords"], "kw1,kw2")
        self.assertEqual(params["sites"], "t.me")
        self.assertEqual(params["timeframe"], "7")
        self.assertEqual(params["team"], "Child Safety")
        self.assertEqual(params["pipeline_run_id"], "run-uuid-1")
        self.assertEqual(run_id, 99999)

        # Should also update the run to 'running'
        update_sql = mock_stmt.call_args[0][0]
        self.assertIn("running", update_sql)
        self.assertIn("99999", update_sql)

    @patch("backend.services.pipeline.run_query")
    def test_get_google_dorking_results_empty(self, mock_query):
        mock_query.side_effect = [
            pd.DataFrame([{"total": 0}]),
            pd.DataFrame(),
        ]

        from backend.services.pipeline import get_google_dorking_results
        page = get_google_dorking_results("run-uuid-1")
        self.assertEqual(page.total, 0)
        self.assertEqual(page.items, [])

    @patch("backend.services.pipeline.run_query")
    def test_get_google_dorking_results_with_rows(self, mock_query):
        results_df = pd.DataFrame([
            {
                "id": "res-1",
                "pipeline_run_id": "run-uuid-1",
                "team": "Child Safety",
                "query": "leaked photos",
                "href": "https://t.me/channel/123",
                "title": "Some Title",
                "body": "Snippet text here",
                "created_at": datetime(2026, 5, 12, 10, 1, tzinfo=timezone.utc),
            }
        ])
        mock_query.side_effect = [pd.DataFrame([{"total": 1}]), results_df]

        from backend.services.pipeline import get_google_dorking_results
        page = get_google_dorking_results("run-uuid-1")

        self.assertEqual(page.total, 1)
        self.assertEqual(len(page.items), 1)
        item = page.items[0]
        self.assertEqual(item.href, "https://t.me/channel/123")
        self.assertEqual(item.title, "Some Title")
        self.assertEqual(item.query, "leaked photos")


# ===========================================================================
# API endpoint tests — TestClient, DB mocked at service level
# ===========================================================================
class TestPipelinesRouter(unittest.TestCase):
    def setUp(self):
        from backend.main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def _run_payload(self, **overrides):
        base = {
            "id": "run-uuid-1",
            "team": "Child Safety",
            "pipeline_type": "google_dorking",
            "config_json": '{"keywords":["test"],"timeframe":30}',
            "status": "running",
            "databricks_run_id": 12345,
            "row_count": None,
            "error_log": None,
            "created_at": "2026-05-12T10:00:00+00:00",
            "created_by": "nikital@activefence.com",
            "completed_at": None,
        }
        base.update(overrides)
        return base

    @patch("backend.services.pipeline.run_query")
    def test_list_runs(self, mock_query):
        mock_query.side_effect = [
            pd.DataFrame([{"total": 0}]),
            pd.DataFrame(),
        ]
        resp = self.client.get("/api/pipelines?team=Child+Safety")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("items", data)
        self.assertEqual(data["total"], 0)

    def test_list_runs_missing_team_param(self):
        resp = self.client.get("/api/pipelines")
        self.assertEqual(resp.status_code, 422)

    def test_list_runs_unknown_team(self):
        resp = self.client.get("/api/pipelines?team=Nonexistent+Team")
        self.assertEqual(resp.status_code, 404)

    @patch("backend.routers.pipelines.trigger_google_dorking_job")
    @patch("backend.routers.pipelines.create_pipeline_run")
    def test_start_pipeline_success(self, mock_create, mock_trigger):
        mock_create.return_value = PipelineRun(**self._run_payload())
        mock_trigger.return_value = 12345

        resp = self.client.post("/api/pipelines", json={
            "team": "Child Safety",
            "pipeline_type": "google_dorking",
            "config": {
                "keywords": ["leaked"],
                "sites": [],
                "clients": [],
                "rule_out": [],
                "timeframe": 30,
                "num_of_results": 100,
                "verbatim": True,
            }
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["team"], "Child Safety")
        self.assertEqual(data["pipeline_type"], "google_dorking")

    def test_start_pipeline_invalid_team(self):
        resp = self.client.post("/api/pipelines", json={
            "team": "Unknown Team",
            "pipeline_type": "google_dorking",
            "config": {"keywords": ["test"], "timeframe": 30, "num_of_results": 10, "verbatim": True},
        })
        self.assertEqual(resp.status_code, 404)

    @patch("backend.routers.pipelines.fail_pipeline_run")
    @patch("backend.routers.pipelines.trigger_google_dorking_job")
    @patch("backend.routers.pipelines.create_pipeline_run")
    def test_start_pipeline_trigger_fails_returns_201_with_failed_status(
        self, mock_create, mock_trigger, mock_fail
    ):
        mock_create.return_value = PipelineRun(**self._run_payload(status="pending", databricks_run_id=None))
        mock_trigger.side_effect = Exception("Databricks job not reachable")

        resp = self.client.post("/api/pipelines", json={
            "team": "Child Safety",
            "pipeline_type": "google_dorking",
            "config": {
                "keywords": ["leaked"],
                "sites": [],
                "clients": [],
                "rule_out": [],
                "timeframe": 30,
                "num_of_results": 100,
                "verbatim": True,
            }
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["status"], "failed")
        self.assertIn("Databricks job not reachable", data["error_log"])
        mock_fail.assert_called_once_with("run-uuid-1", "Databricks job not reachable")

    def test_start_pipeline_empty_keywords_rejected(self):
        resp = self.client.post("/api/pipelines", json={
            "team": "Child Safety",
            "pipeline_type": "google_dorking",
            "config": {"keywords": [], "timeframe": 30, "num_of_results": 10, "verbatim": True},
        })
        # keywords is a required non-empty list — Pydantic should reject
        self.assertIn(resp.status_code, [422])

    @patch("backend.services.pipeline.run_query")
    def test_get_run_not_found(self, mock_query):
        mock_query.return_value = pd.DataFrame()
        resp = self.client.get("/api/pipelines/nonexistent-id")
        self.assertEqual(resp.status_code, 404)

    @patch("backend.services.pipeline.run_query")
    def test_get_results_run_not_found(self, mock_query):
        mock_query.return_value = pd.DataFrame()
        resp = self.client.get("/api/pipelines/nonexistent-id/results")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
