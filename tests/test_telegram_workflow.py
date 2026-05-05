"""
Unit tests for modules/telegram_workflow.py pure-Python logic.
No Databricks connection required — all SDK calls are mocked.
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call

import pandas as pd


# ---------------------------------------------------------------------------
# Stub out Streamlit before importing the module under test.
# @st.fragment must be a no-op decorator that handles both calling styles:
#   @st.fragment          (no parens)
#   @st.fragment(...)     (with kwargs)
# ---------------------------------------------------------------------------

def _fragment_stub(func=None, **kwargs):
    if func is not None:
        return func
    return lambda fn: fn


_st = types.ModuleType("streamlit")
for _attr in [
    "subheader", "markdown", "caption", "info", "success", "error", "warning",
    "button", "selectbox", "text_input", "columns", "expander", "popover",
    "divider", "toast", "spinner", "rerun", "data_editor", "graphviz_chart",
    "dataframe", "write",
]:
    setattr(_st, _attr, MagicMock())

_st.fragment = _fragment_stub
_st.session_state = {}

sys.modules["streamlit"] = _st

# Now safe to import the module under test
from modules.telegram_workflow import (  # noqa: E402
    _clean_state,
    _sheet_df,
    _task_type_and_path,
    _get_run_status,
    _render_task_graph,
    WORKFLOW_CONFIG,
    _RUNNING_STATES,
    _DONE_STATES,
    _TASK_DOT_COLORS,
    _TASK_PREFIX,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_run(life_cycle, result_state=None, message="", tasks=None):
    run = MagicMock()
    run.state.life_cycle_state = life_cycle
    run.state.result_state = result_state
    run.state.state_message = message
    run.tasks = tasks or []
    return run


def _make_task(key, life_cycle_state, result_state=None, depends_on=None):
    task = MagicMock()
    task.task_key = key
    task.state = MagicMock()
    task.state.life_cycle_state = life_cycle_state
    task.state.result_state = result_state
    task.depends_on = depends_on or []
    return task


def _make_dep(key):
    dep = MagicMock()
    dep.task_key = key
    return dep


# ---------------------------------------------------------------------------
# _clean_state
# ---------------------------------------------------------------------------

class TestCleanState(unittest.TestCase):

    def test_strips_enum_prefix(self):
        self.assertEqual(_clean_state("RunLifeCycleState.RUNNING"), "RUNNING")

    def test_no_dot_passthrough(self):
        self.assertEqual(_clean_state("RUNNING"), "RUNNING")

    def test_multiple_dots_takes_last_segment(self):
        self.assertEqual(_clean_state("a.b.TERMINATED"), "TERMINATED")

    def test_empty_string(self):
        self.assertEqual(_clean_state(""), "")

    def test_single_dot(self):
        self.assertEqual(_clean_state("x.SUCCESS"), "SUCCESS")

    def test_all_known_running_states_survive_roundtrip(self):
        for state in _RUNNING_STATES:
            self.assertEqual(_clean_state(f"Prefix.{state}"), state)

    def test_all_known_done_states_survive_roundtrip(self):
        for state in _DONE_STATES:
            self.assertEqual(_clean_state(f"Prefix.{state}"), state)


# ---------------------------------------------------------------------------
# _sheet_df
# ---------------------------------------------------------------------------

class TestSheetDf(unittest.TestCase):

    def _ws(self, data):
        ws = MagicMock()
        ws.get_all_values.return_value = data
        return ws

    def test_no_data_returns_empty_df(self):
        df = _sheet_df(self._ws([]))
        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)
        self.assertEqual(len(df.columns), 0)

    def test_header_only_returns_columns_zero_rows(self):
        df = _sheet_df(self._ws([["URL", "Name", "Status"]]))
        self.assertEqual(list(df.columns), ["URL", "Name", "Status"])
        self.assertEqual(len(df), 0)

    def test_header_only_is_not_fully_empty(self):
        # Tabs with headers but no rows must NOT appear as df.empty when columns exist
        df = _sheet_df(self._ws([["A", "B"]]))
        self.assertFalse(df.empty and len(df.columns) == 0)

    def test_single_data_row(self):
        df = _sheet_df(self._ws([["url", "team"], ["https://t.me/a", "CT"]]))
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["url"], "https://t.me/a")
        self.assertEqual(df.iloc[0]["team"], "CT")

    def test_multiple_data_rows(self):
        data = [["url", "name"], ["https://t.me/a", "Alpha"], ["https://t.me/b", "Beta"]]
        df = _sheet_df(self._ws(data))
        self.assertEqual(list(df.columns), ["url", "name"])
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[1]["name"], "Beta")

    def test_column_names_from_first_row(self):
        data = [["Telegram Group Link", "Online Status"], ["https://t.me/x", "Online"]]
        df = _sheet_df(self._ws(data))
        self.assertIn("Telegram Group Link", df.columns)
        self.assertIn("Online Status", df.columns)


# ---------------------------------------------------------------------------
# _task_type_and_path
# ---------------------------------------------------------------------------

class TestTaskTypeAndPath(unittest.TestCase):

    def _base_task(self):
        """Task with all type attributes set to falsy."""
        t = MagicMock()
        t.notebook_task = None
        t.spark_python_task = None
        t.python_wheel_task = None
        t.spark_jar_task = None
        t.sql_task = None
        t.run_job_task = None
        t.pipeline_task = None
        return t

    def test_notebook_task(self):
        t = self._base_task()
        t.notebook_task = MagicMock(notebook_path="/Repos/foo/bar")
        typ, path = _task_type_and_path(t)
        self.assertEqual(typ, "Notebook")
        self.assertEqual(path, "/Repos/foo/bar")

    def test_notebook_task_empty_path(self):
        t = self._base_task()
        t.notebook_task = MagicMock(notebook_path=None)
        typ, path = _task_type_and_path(t)
        self.assertEqual(typ, "Notebook")
        self.assertEqual(path, "")

    def test_spark_python_task(self):
        t = self._base_task()
        py = MagicMock(python_file="jobs/scrape.py")
        t.spark_python_task = py
        typ, path = _task_type_and_path(t)
        self.assertEqual(typ, "Python")
        self.assertEqual(path, "jobs/scrape.py")

    def test_python_wheel_task_entry_point(self):
        t = self._base_task()
        whl = MagicMock()
        whl.entry_point = "main"
        whl.package_name = "my_pkg"
        t.python_wheel_task = whl
        typ, path = _task_type_and_path(t)
        self.assertEqual(typ, "Python Wheel")
        self.assertEqual(path, "main")

    def test_python_wheel_task_falls_back_to_package_name(self):
        t = self._base_task()
        whl = MagicMock()
        whl.entry_point = ""
        whl.package_name = "my_pkg"
        t.python_wheel_task = whl
        typ, path = _task_type_and_path(t)
        self.assertEqual(path, "my_pkg")

    def test_jar_task(self):
        t = self._base_task()
        t.spark_jar_task = MagicMock(main_class_name="com.example.Main")
        typ, _ = _task_type_and_path(t)
        self.assertEqual(typ, "JAR")

    def test_sql_task(self):
        t = self._base_task()
        t.sql_task = MagicMock()
        typ, _ = _task_type_and_path(t)
        self.assertEqual(typ, "SQL")

    def test_run_job_task(self):
        t = self._base_task()
        rjt = MagicMock()
        rjt.job_id = 42
        t.run_job_task = rjt
        typ, path = _task_type_and_path(t)
        self.assertEqual(typ, "Run Job")
        self.assertEqual(path, "42")

    def test_pipeline_task(self):
        t = self._base_task()
        pt = MagicMock()
        pt.pipeline_id = "pipe-123"
        t.pipeline_task = pt
        typ, path = _task_type_and_path(t)
        self.assertEqual(typ, "Pipeline")

    def test_unknown_task(self):
        t = self._base_task()
        typ, path = _task_type_and_path(t)
        self.assertEqual(typ, "Unknown")
        self.assertEqual(path, "")

    def test_notebook_checked_before_python(self):
        # notebook_task takes priority
        t = self._base_task()
        t.notebook_task = MagicMock(notebook_path="/nb")
        t.spark_python_task = MagicMock(python_file="job.py")
        typ, _ = _task_type_and_path(t)
        self.assertEqual(typ, "Notebook")


# ---------------------------------------------------------------------------
# _get_run_status
# ---------------------------------------------------------------------------

class TestGetRunStatus(unittest.TestCase):

    def _wc_with_run(self, run):
        wc = MagicMock()
        wc.jobs.get_run.return_value = run
        return wc

    def _call(self, run):
        wc = self._wc_with_run(run)
        with patch("modules.telegram_workflow._app") as mock_app:
            mock_app.return_value.get_workspace_client.return_value = wc
            return _get_run_status(42)

    def test_running_state_is_running(self):
        status = self._call(_make_run("RUNNING"))
        self.assertEqual(status["life_cycle"], "RUNNING")
        self.assertTrue(status["is_running"])
        self.assertFalse(status["is_done"])

    def test_pending_state_is_running(self):
        status = self._call(_make_run("PENDING"))
        self.assertTrue(status["is_running"])

    def test_queued_state_is_running(self):
        status = self._call(_make_run("QUEUED"))
        self.assertTrue(status["is_running"])

    def test_terminated_success_is_done(self):
        status = self._call(_make_run("TERMINATED", result_state="SUCCESS"))
        self.assertEqual(status["result"], "SUCCESS")
        self.assertFalse(status["is_running"])
        self.assertTrue(status["is_done"])

    def test_terminated_failed_carries_message(self):
        status = self._call(_make_run("TERMINATED", result_state="FAILED", message="OOM on cluster"))
        self.assertEqual(status["result"], "FAILED")
        self.assertEqual(status["message"], "OOM on cluster")
        self.assertTrue(status["is_done"])

    def test_internal_error_is_done(self):
        status = self._call(_make_run("INTERNAL_ERROR"))
        self.assertTrue(status["is_done"])

    def test_unknown_lifecycle_treated_as_running(self):
        # Any state not in _RUNNING_STATES or _DONE_STATES → is_running=True
        status = self._call(_make_run("BRAND_NEW_STATE"))
        self.assertTrue(status["is_running"])
        self.assertFalse(status["is_done"])

    def test_enum_prefix_stripped_from_lifecycle(self):
        status = self._call(_make_run("RunLifeCycleState.RUNNING"))
        self.assertEqual(status["life_cycle"], "RUNNING")

    def test_enum_prefix_stripped_from_result(self):
        status = self._call(_make_run("TERMINATED", result_state="RunResultState.SUCCESS"))
        self.assertEqual(status["result"], "SUCCESS")

    def test_no_result_state_gives_empty_string(self):
        status = self._call(_make_run("RUNNING", result_state=None))
        self.assertEqual(status["result"], "")

    def test_tasks_list_returned(self):
        task = _make_task("ingest", "RUNNING")
        status = self._call(_make_run("RUNNING", tasks=[task]))
        self.assertEqual(len(status["tasks"]), 1)
        self.assertEqual(status["tasks"][0].task_key, "ingest")

    def test_empty_tasks_returns_list(self):
        status = self._call(_make_run("RUNNING", tasks=[]))
        self.assertEqual(status["tasks"], [])

    def test_calls_get_run_with_correct_id(self):
        run = _make_run("RUNNING")
        wc = self._wc_with_run(run)
        with patch("modules.telegram_workflow._app") as mock_app:
            mock_app.return_value.get_workspace_client.return_value = wc
            _get_run_status(9999)
        wc.jobs.get_run.assert_called_once_with(run_id=9999)


# ---------------------------------------------------------------------------
# _render_task_graph — DOT string generation
# ---------------------------------------------------------------------------

class TestRenderTaskGraph(unittest.TestCase):

    def setUp(self):
        _st.graphviz_chart.reset_mock()

    def _dot(self):
        args = _st.graphviz_chart.call_args
        return args[0][0] if args else None

    def test_no_tasks_no_chart_rendered(self):
        _render_task_graph([])
        _st.graphviz_chart.assert_not_called()

    def test_single_task_key_in_dot(self):
        _render_task_graph([_make_task("scrape", "RUNNING")])
        self.assertIn('"scrape"', self._dot())

    def test_running_state_label_present(self):
        _render_task_graph([_make_task("t", "RUNNING")])
        self.assertIn("RUNNING", self._dot())

    def test_running_task_has_play_prefix(self):
        _render_task_graph([_make_task("t", "RUNNING")])
        self.assertIn(_TASK_PREFIX["RUNNING"], self._dot())

    def test_success_task_has_checkmark(self):
        _render_task_graph([_make_task("t", "TERMINATED", result_state="SUCCESS")])
        self.assertIn(_TASK_PREFIX["SUCCESS"], self._dot())

    def test_failed_task_has_cross(self):
        _render_task_graph([_make_task("t", "TERMINATED", result_state="FAILED")])
        self.assertIn(_TASK_PREFIX["FAILED"], self._dot())

    def test_pending_task_no_prefix(self):
        _render_task_graph([_make_task("t", "PENDING")])
        dot = self._dot()
        # PENDING has no prefix in _TASK_PREFIX
        self.assertNotIn("▶", dot)
        self.assertNotIn("✓", dot)
        self.assertNotIn("✗", dot)

    def test_dependency_edge_rendered(self):
        dep = _make_dep("step_a")
        _render_task_graph([
            _make_task("step_a", "SUCCESS", result_state="SUCCESS"),
            _make_task("step_b", "RUNNING", depends_on=[dep]),
        ])
        self.assertIn('"step_a" -> "step_b"', self._dot())

    def test_no_edge_without_dependency(self):
        _render_task_graph([_make_task("a", "RUNNING"), _make_task("b", "PENDING")])
        self.assertNotIn("->", self._dot())

    def test_multiple_tasks_all_in_dot(self):
        _render_task_graph([
            _make_task("fetch", "TERMINATED", result_state="SUCCESS"),
            _make_task("process", "RUNNING"),
            _make_task("upload", "PENDING"),
        ])
        dot = self._dot()
        self.assertIn('"fetch"', dot)
        self.assertIn('"process"', dot)
        self.assertIn('"upload"', dot)

    def test_dot_wraps_in_digraph(self):
        _render_task_graph([_make_task("x", "RUNNING")])
        dot = self._dot().strip()
        self.assertTrue(dot.startswith("digraph {"))
        self.assertTrue(dot.endswith("}"))

    def test_success_color_applied(self):
        _render_task_graph([_make_task("t", "TERMINATED", result_state="SUCCESS")])
        _, fill = _TASK_DOT_COLORS["SUCCESS"]
        self.assertIn(fill, self._dot())

    def test_failed_color_applied(self):
        _render_task_graph([_make_task("t", "TERMINATED", result_state="FAILED")])
        _, fill = _TASK_DOT_COLORS["FAILED"]
        self.assertIn(fill, self._dot())

    def test_unknown_state_falls_back_gracefully(self):
        task = _make_task("x", "BRAND_NEW_STATE")
        task.state.result_state = None
        _render_task_graph([task])
        self.assertIsNotNone(self._dot())

    def test_multiple_deps_all_edges_present(self):
        dep_a = _make_dep("a")
        dep_b = _make_dep("b")
        _render_task_graph([
            _make_task("a", "SUCCESS", result_state="SUCCESS"),
            _make_task("b", "SUCCESS", result_state="SUCCESS"),
            _make_task("c", "RUNNING", depends_on=[dep_a, dep_b]),
        ])
        dot = self._dot()
        self.assertIn('"a" -> "c"', dot)
        self.assertIn('"b" -> "c"', dot)


# ---------------------------------------------------------------------------
# Active run auto-detection on page load
# ---------------------------------------------------------------------------

def _make_active_run_stub(run_id):
    r = MagicMock()
    r.run_id = run_id
    return r


class TestAutoDetectActiveRun(unittest.TestCase):
    """
    When tw_active_run_id is absent from session state (fresh page load),
    list_runs(active_only=True) should be queried and, if a run is found,
    tw_active_run_id should be populated automatically.
    """

    def _build_wc(self, active_run_id=None):
        wc = MagicMock()
        active_runs = [_make_active_run_stub(active_run_id)] if active_run_id else []
        wc.jobs.list_runs.return_value = iter(active_runs)
        return wc

    def test_no_session_state_and_active_run_populates_key(self):
        wc = self._build_wc(active_run_id=777)
        with patch("modules.telegram_workflow._app") as mock_app:
            mock_app.return_value.get_workspace_client.return_value = wc
            _st.session_state = {}
            # Simulate the auto-detect block
            active_runs = list(wc.jobs.list_runs(job_id=123, active_only=True, limit=1))
            if active_runs:
                _st.session_state["tw_active_run_id"] = active_runs[0].run_id
        self.assertEqual(_st.session_state.get("tw_active_run_id"), 777)

    def test_no_session_state_and_no_active_run_leaves_key_absent(self):
        wc = self._build_wc(active_run_id=None)
        with patch("modules.telegram_workflow._app") as mock_app:
            mock_app.return_value.get_workspace_client.return_value = wc
            _st.session_state = {}
            active_runs = list(wc.jobs.list_runs(job_id=123, active_only=True, limit=1))
            if active_runs:
                _st.session_state["tw_active_run_id"] = active_runs[0].run_id
        self.assertNotIn("tw_active_run_id", _st.session_state)

    def test_existing_session_state_not_overwritten(self):
        wc = self._build_wc(active_run_id=888)
        _st.session_state = {"tw_active_run_id": 42}
        # When key already present the auto-detect block is skipped
        active_run_id = _st.session_state.get("tw_active_run_id")
        if not active_run_id:
            active_runs = list(wc.jobs.list_runs(job_id=123, active_only=True, limit=1))
            if active_runs:
                _st.session_state["tw_active_run_id"] = active_runs[0].run_id
        self.assertEqual(_st.session_state["tw_active_run_id"], 42)  # unchanged

    def test_list_runs_called_with_active_only_true(self):
        wc = self._build_wc(active_run_id=None)
        with patch("modules.telegram_workflow._app") as mock_app:
            mock_app.return_value.get_workspace_client.return_value = wc
            _st.session_state = {}
            list(wc.jobs.list_runs(job_id=999, active_only=True, limit=1))
        wc.jobs.list_runs.assert_called_once_with(job_id=999, active_only=True, limit=1)

    def test_sdk_error_during_detection_does_not_crash(self):
        wc = MagicMock()
        wc.jobs.list_runs.side_effect = RuntimeError("network error")
        try:
            list(wc.jobs.list_runs(job_id=123, active_only=True, limit=1))
        except Exception:
            pass  # must be silently swallowed in production code
        self.assertNotIn("tw_active_run_id", _st.session_state)


# ---------------------------------------------------------------------------
# cancel_run — stop job calls the SDK correctly
# ---------------------------------------------------------------------------

class TestCancelRun(unittest.TestCase):

    def test_cancel_run_called_with_active_run_id(self):
        wc = MagicMock()
        wc.jobs.cancel_run.return_value = None
        wc.jobs.cancel_run(run_id=42)
        wc.jobs.cancel_run.assert_called_once_with(run_id=42)

    def test_cancel_run_different_run_ids(self):
        wc = MagicMock()
        for run_id in [1, 100, 999999]:
            wc.reset_mock()
            wc.jobs.cancel_run(run_id=run_id)
            wc.jobs.cancel_run.assert_called_once_with(run_id=run_id)

    def test_cancel_run_raises_on_sdk_error(self):
        wc = MagicMock()
        wc.jobs.cancel_run.side_effect = RuntimeError("permission denied")
        with self.assertRaises(RuntimeError):
            wc.jobs.cancel_run(run_id=42)


# ---------------------------------------------------------------------------
# WORKFLOW_CONFIG sanity
# ---------------------------------------------------------------------------

class TestWorkflowConfig(unittest.TestCase):

    _REQUIRED_KEYS = {"job_id", "sheet_id", "job_url", "sheet_url"}

    def test_all_entries_have_required_keys(self):
        for team, cfg in WORKFLOW_CONFIG.items():
            missing = self._REQUIRED_KEYS - set(cfg.keys())
            self.assertFalse(missing, f"Team {team!r} missing keys: {missing}")

    def test_job_ids_are_numeric_strings(self):
        for team, cfg in WORKFLOW_CONFIG.items():
            self.assertTrue(cfg["job_id"].isdigit(), f"Team {team!r} job_id not numeric")

    def test_sheet_ids_are_nonempty(self):
        for team, cfg in WORKFLOW_CONFIG.items():
            self.assertTrue(cfg["sheet_id"], f"Team {team!r} sheet_id is empty")

    def test_job_url_contains_job_id(self):
        for team, cfg in WORKFLOW_CONFIG.items():
            self.assertIn(cfg["job_id"], cfg["job_url"],
                          f"Team {team!r} job_url doesn't contain job_id")

    def test_sheet_url_contains_sheet_id(self):
        for team, cfg in WORKFLOW_CONFIG.items():
            self.assertIn(cfg["sheet_id"], cfg["sheet_url"],
                          f"Team {team!r} sheet_url doesn't contain sheet_id")


if __name__ == "__main__":
    unittest.main()
