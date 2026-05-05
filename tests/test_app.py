"""
Unit tests for app.py and pages/import_sources.py pure-Python logic.
No Databricks connection required — all DB calls are mocked where needed.
"""
import io
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

# ---------------------------------------------------------------------------
# Stub out Streamlit and Databricks SDK before importing app
# ---------------------------------------------------------------------------

# Minimal streamlit stub so the module-level st.set_page_config / st.sidebar
# calls don't crash during import.

def _selectbox(label, options, *args, **kwargs):
    """Return first option so PAGES[selected_page] resolves on import."""
    if options:
        return options[0]
    return MagicMock()

_sidebar = MagicMock()
_sidebar.selectbox = _selectbox
_sidebar.form.return_value.__enter__ = lambda s: s
_sidebar.form.return_value.__exit__ = MagicMock(return_value=False)

_st = types.ModuleType("streamlit")
for _attr in [
    "set_page_config", "cache_data", "cache_resource",
    "title", "info", "success", "error", "warning", "caption", "divider",
    "columns", "expander", "dataframe", "text_input", "text_area",
    "selectbox", "multiselect", "checkbox", "form", "form_submit_button",
    "button", "download_button", "progress", "spinner", "subheader",
    "bar_chart", "line_chart", "metric", "json", "tabs", "file_uploader",
    "header", "dialog", "data_editor", "column_config", "code", "rerun",
    "write",
]:
    setattr(_st, _attr, MagicMock(return_value=MagicMock()))

_st.selectbox = _selectbox
_st.sidebar = _sidebar
_st.session_state = {}

# st.cache_data / st.cache_resource must be usable as decorators that are no-ops.
_st.cache_data = lambda *a, **kw: (lambda fn: fn)
_st.cache_resource = lambda fn: fn
# st.dialog must work as a decorator factory: @st.dialog("title") → no-op decorator
_st.dialog = lambda *a, **kw: (lambda fn: fn)
sys.modules["streamlit"] = _st

# Stub databricks.sql
_dbsql_mod = types.ModuleType("databricks.sql")
_dbsql_mod.connect = MagicMock()
sys.modules.setdefault("databricks", types.ModuleType("databricks"))
sys.modules["databricks.sql"] = _dbsql_mod

# Stub databricks.sdk
_sdk_mod = types.ModuleType("databricks.sdk")
_sdk_mod.WorkspaceClient = MagicMock()
sys.modules["databricks.sdk"] = _sdk_mod

import app  # noqa: E402  (must come after stubs)
import pages.import_sources as imp  # noqa: E402


# ---------------------------------------------------------------------------
# detect_platform_from_url
# ---------------------------------------------------------------------------

class TestDetectPlatformFromUrl(unittest.TestCase):

    def test_telegram_t_me(self):
        self.assertEqual(app.detect_platform_from_url("https://t.me/somechannel"), "Telegram")

    def test_telegram_telegram_me(self):
        self.assertEqual(app.detect_platform_from_url("https://telegram.me/channel"), "Telegram")

    def test_twitter(self):
        self.assertEqual(app.detect_platform_from_url("https://twitter.com/user"), "Twitter/X")

    def test_x_com(self):
        self.assertEqual(app.detect_platform_from_url("https://x.com/user"), "Twitter/X")

    def test_tiktok(self):
        self.assertEqual(app.detect_platform_from_url("https://www.tiktok.com/@user"), "TikTok")

    def test_instagram(self):
        self.assertEqual(app.detect_platform_from_url("https://instagram.com/user"), "Instagram")

    def test_instagr_am(self):
        self.assertEqual(app.detect_platform_from_url("https://instagr.am/p/abc"), "Instagram")

    def test_youtube(self):
        self.assertEqual(app.detect_platform_from_url("https://youtube.com/watch?v=abc"), "YouTube")

    def test_youtu_be(self):
        self.assertEqual(app.detect_platform_from_url("https://youtu.be/abc"), "YouTube")

    def test_facebook(self):
        self.assertEqual(app.detect_platform_from_url("https://facebook.com/page"), "Facebook")

    def test_fb_com(self):
        self.assertEqual(app.detect_platform_from_url("https://fb.com/page"), "Facebook")

    def test_fb_watch(self):
        self.assertEqual(app.detect_platform_from_url("https://fb.watch/abc"), "Facebook")

    def test_unknown(self):
        self.assertEqual(app.detect_platform_from_url("https://example.com"), "Unknown")

    def test_empty_string(self):
        self.assertEqual(app.detect_platform_from_url(""), "Unknown")

    def test_none_like_empty(self):
        self.assertEqual(app.detect_platform_from_url(None), "Unknown")

    def test_case_insensitive(self):
        self.assertEqual(app.detect_platform_from_url("HTTPS://T.ME/Channel"), "Telegram")


# ---------------------------------------------------------------------------
# detect_platform_from_column_name
# ---------------------------------------------------------------------------

class TestDetectPlatformFromColumnName(unittest.TestCase):

    def test_telegram_column(self):
        self.assertEqual(app.detect_platform_from_column_name("telegram_link"), "Telegram")

    def test_twitter_column(self):
        self.assertEqual(app.detect_platform_from_column_name("Twitter Handle"), "Twitter/X")

    def test_tweet_column(self):
        self.assertEqual(app.detect_platform_from_column_name("tweet_url"), "Twitter/X")

    def test_tiktok_column(self):
        self.assertEqual(app.detect_platform_from_column_name("TikTok Profile"), "TikTok")

    def test_instagram_column(self):
        self.assertEqual(app.detect_platform_from_column_name("insta_url"), "Instagram")

    def test_youtube_column(self):
        self.assertEqual(app.detect_platform_from_column_name("YouTube_link"), "YouTube")

    def test_facebook_column(self):
        self.assertEqual(app.detect_platform_from_column_name("Facebook Page"), "Facebook")

    def test_no_match_returns_none(self):
        self.assertIsNone(app.detect_platform_from_column_name("source"))

    def test_no_match_generic_url(self):
        self.assertIsNone(app.detect_platform_from_column_name("url"))


# ---------------------------------------------------------------------------
# _parse_gsheet_url
# ---------------------------------------------------------------------------

class TestParseGsheetUrl(unittest.TestCase):

    def test_full_url_with_gid(self):
        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit#gid=0"
        sheet_id, gid = app._parse_gsheet_url(url)
        self.assertEqual(sheet_id, "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms")
        self.assertEqual(gid, 0)

    def test_url_without_gid(self):
        url = "https://docs.google.com/spreadsheets/d/ABCDEF123/edit"
        sheet_id, gid = app._parse_gsheet_url(url)
        self.assertEqual(sheet_id, "ABCDEF123")
        self.assertIsNone(gid)

    def test_url_with_non_zero_gid(self):
        url = "https://docs.google.com/spreadsheets/d/XYZ/edit#gid=1234567890"
        _, gid = app._parse_gsheet_url(url)
        self.assertEqual(gid, 1234567890)

    def test_invalid_url_raises(self):
        with self.assertRaises(ValueError):
            app._parse_gsheet_url("https://example.com/not-a-sheet")


# ---------------------------------------------------------------------------
# _fix_sa_private_key
# ---------------------------------------------------------------------------

class TestFixSaPrivateKey(unittest.TestCase):

    def test_already_formatted_key_unchanged(self):
        key = "-----BEGIN PRIVATE KEY-----\nABCD\n-----END PRIVATE KEY-----\n"
        d = {"private_key": key}
        result = app._fix_sa_private_key(d)
        self.assertEqual(result["private_key"], key)

    def test_single_line_key_gets_wrapped(self):
        # Simulate a key with no \n between header/footer
        content = "A" * 128
        flat_key = f"-----BEGIN PRIVATE KEY-----{content}-----END PRIVATE KEY-----"
        d = {"private_key": flat_key}
        result = app._fix_sa_private_key(d)
        pk = result["private_key"]
        self.assertIn("\n", pk)
        self.assertTrue(pk.startswith("-----BEGIN PRIVATE KEY-----\n"))
        self.assertTrue(pk.strip().endswith("-----END PRIVATE KEY-----"))
        # Check 64-char line wrapping
        body_lines = pk.split("\n")[1:-2]  # strip header, footer, trailing empty
        for line in body_lines:
            self.assertLessEqual(len(line), 64)

    def test_missing_key_no_crash(self):
        d = {}
        result = app._fix_sa_private_key(d)
        self.assertEqual(result, {})

    def test_empty_key_no_crash(self):
        d = {"private_key": ""}
        result = app._fix_sa_private_key(d)
        self.assertEqual(result["private_key"], "")


# ---------------------------------------------------------------------------
# _auto_map  (pages/import_sources.py)
# ---------------------------------------------------------------------------

class TestAutoMap(unittest.TestCase):

    def test_maps_url_column(self):
        mapping = imp._auto_map(["URL", "Team", "Notes"])
        self.assertEqual(mapping["url"], "URL")

    def test_maps_link_column_to_url(self):
        mapping = imp._auto_map(["link", "team"])
        self.assertEqual(mapping["url"], "link")

    def test_maps_team(self):
        mapping = imp._auto_map(["source_url", "team_name"])
        self.assertEqual(mapping["team"], "team_name")

    def test_maps_notes(self):
        mapping = imp._auto_map(["url", "comment"])
        self.assertEqual(mapping["notes"], "comment")

    def test_maps_abuse_area(self):
        mapping = imp._auto_map(["url", "abuse_area"])
        self.assertEqual(mapping["abuse_area"], "abuse_area")

    def test_maps_relevancy(self):
        mapping = imp._auto_map(["url", "relevancy_score"])
        self.assertEqual(mapping["relevancy"], "relevancy_score")

    def test_unrecognised_columns_map_to_none(self):
        mapping = imp._auto_map(["foo", "bar", "baz"])
        self.assertIsNone(mapping["url"])
        self.assertIsNone(mapping["team"])

    def test_first_match_wins(self):
        # Both 'link' and 'url' match the url field; first column encountered wins
        mapping = imp._auto_map(["link", "url_address"])
        self.assertEqual(mapping["url"], "link")


# ---------------------------------------------------------------------------
# _safe_val  (pages/import_sources.py)
# ---------------------------------------------------------------------------

class TestSafeVal(unittest.TestCase):

    def test_normal_value(self):
        row = {"url": "https://t.me/channel"}
        self.assertEqual(imp._safe_val(row, "url"), "https://t.me/channel")

    def test_nan_becomes_empty(self):
        import math
        row = {"url": float("nan")}
        self.assertEqual(imp._safe_val(row, "url"), "")

    def test_none_value_becomes_empty(self):
        row = {"url": None}
        self.assertEqual(imp._safe_val(row, "url"), "")

    def test_missing_column_becomes_empty(self):
        row = {}
        self.assertEqual(imp._safe_val(row, "url"), "")

    def test_none_col_arg_becomes_empty(self):
        row = {"url": "something"}
        self.assertEqual(imp._safe_val(row, None), "")

    def test_string_none_becomes_empty(self):
        row = {"url": "None"}
        self.assertEqual(imp._safe_val(row, "url"), "")

    def test_string_nan_becomes_empty(self):
        row = {"url": "nan"}
        self.assertEqual(imp._safe_val(row, "url"), "")


# ---------------------------------------------------------------------------
# get_multivalue_options
# ---------------------------------------------------------------------------

class TestGetMultivalueOptions(unittest.TestCase):

    def test_single_values(self):
        df = pd.DataFrame({"team": ["CT", "HS", "CT"]})
        opts = app.get_multivalue_options(df, "team")
        self.assertEqual(sorted(opts), ["CT", "HS"])

    def test_comma_separated(self):
        df = pd.DataFrame({"abuse_area": ["CSAM, TFGBV", "CSAM", "Extremism"]})
        opts = app.get_multivalue_options(df, "abuse_area")
        self.assertIn("CSAM", opts)
        self.assertIn("TFGBV", opts)
        self.assertIn("Extremism", opts)

    def test_empty_and_nan_ignored(self):
        df = pd.DataFrame({"team": [None, "", "CT"]})
        opts = app.get_multivalue_options(df, "team")
        self.assertEqual(opts, ["CT"])

    def test_sorted_output(self):
        df = pd.DataFrame({"team": ["Z", "A", "M"]})
        opts = app.get_multivalue_options(df, "team")
        self.assertEqual(opts, sorted(opts))


# ---------------------------------------------------------------------------
# multivalue_mask
# ---------------------------------------------------------------------------

class TestMultivalueMask(unittest.TestCase):

    def test_exact_match(self):
        s = pd.Series(["CT", "HS", "CS"])
        mask = app.multivalue_mask(s, ["CT"])
        self.assertTrue(mask.iloc[0])
        self.assertFalse(mask.iloc[1])
        self.assertFalse(mask.iloc[2])

    def test_comma_separated_partial_match(self):
        s = pd.Series(["CT, HS", "CS", "HS"])
        mask = app.multivalue_mask(s, ["HS"])
        self.assertTrue(mask.iloc[0])
        self.assertFalse(mask.iloc[1])
        self.assertTrue(mask.iloc[2])

    def test_multiple_selected(self):
        s = pd.Series(["CT", "HS", "CS", "CT, CS"])
        mask = app.multivalue_mask(s, ["CT", "CS"])
        self.assertTrue(mask.iloc[0])
        self.assertFalse(mask.iloc[1])
        self.assertTrue(mask.iloc[2])
        self.assertTrue(mask.iloc[3])

    def test_nan_returns_false(self):
        s = pd.Series([None, float("nan"), "CT"])
        mask = app.multivalue_mask(s, ["CT"])
        self.assertFalse(mask.iloc[0])
        self.assertFalse(mask.iloc[1])
        self.assertTrue(mask.iloc[2])

    def test_empty_string_returns_false(self):
        s = pd.Series([""])
        mask = app.multivalue_mask(s, ["CT"])
        self.assertFalse(mask.iloc[0])


# ---------------------------------------------------------------------------
# _parse_paste  (pages/import_sources.py)
# ---------------------------------------------------------------------------

class TestParsePaste(unittest.TestCase):

    def test_tab_separated(self):
        text = "url\tteam\nhttps://t.me/a\tCT\nhttps://x.com/b\tHS"
        df = imp._parse_paste(text)
        self.assertIsNotNone(df)
        self.assertEqual(list(df.columns), ["url", "team"])
        self.assertEqual(len(df), 2)

    def test_csv_separated(self):
        text = "url,team\nhttps://t.me/a,CT"
        df = imp._parse_paste(text)
        self.assertIsNotNone(df)
        self.assertIn("url", df.columns)

    def test_semicolon_separated(self):
        text = "url;team\nhttps://t.me/a;CT"
        df = imp._parse_paste(text)
        self.assertIsNotNone(df)

    def test_single_column_returns_none(self):
        # Only one column — not enough to be useful
        text = "url\nhttps://t.me/a\nhttps://x.com/b"
        result = imp._parse_paste(text)
        self.assertIsNone(result)

    def test_empty_returns_none(self):
        result = imp._parse_paste("   ")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _get_gsheets_client — local file path branch
# ---------------------------------------------------------------------------

class TestGetGsheetsClientLocalFile(unittest.TestCase):

    def _make_gspread_stub(self):
        gspread_mod = types.ModuleType("gspread")
        gspread_mod.authorize = MagicMock(return_value=MagicMock(name="gspread_client"))
        return gspread_mod

    def _make_oauth2_stub(self):
        oauth2_mod = types.ModuleType("oauth2client.service_account")
        fake_creds = MagicMock(name="ServiceAccountCredentials")
        oauth2_mod.ServiceAccountCredentials = MagicMock(
            from_json_keyfile_name=MagicMock(return_value=fake_creds),
            from_json_keyfile_dict=MagicMock(return_value=fake_creds),
        )
        return oauth2_mod, fake_creds

    def test_uses_local_file_when_it_exists(self):
        gspread_mod = self._make_gspread_stub()
        oauth2_mod, fake_creds = self._make_oauth2_stub()

        with patch.dict("os.environ", {"GOOGLE_SERVICE_ACCOUNT_PATH": "/tmp/sa.json"}), \
             patch("os.path.exists", return_value=True), \
             patch.dict(sys.modules, {
                 "gspread": gspread_mod,
                 "oauth2client": types.ModuleType("oauth2client"),
                 "oauth2client.service_account": oauth2_mod,
             }):
            client = app._get_gsheets_client()

        oauth2_mod.ServiceAccountCredentials.from_json_keyfile_name.assert_called_once_with(
            "/tmp/sa.json", unittest.mock.ANY
        )
        gspread_mod.authorize.assert_called_once_with(fake_creds)
        self.assertIsNotNone(client)

    def test_falls_back_to_workspace_client_when_no_local_file(self):
        import base64
        import json

        sa_dict = {
            "type": "service_account",
            "private_key": "-----BEGIN PRIVATE KEY-----\nABC\n-----END PRIVATE KEY-----\n",
            "client_email": "sa@project.iam.gserviceaccount.com",
        }
        encoded = base64.b64encode(json.dumps(sa_dict).encode()).decode()

        mock_ws_client = MagicMock()
        mock_ws_client.workspace.export.return_value.content = encoded

        gspread_mod = self._make_gspread_stub()
        oauth2_mod, fake_creds = self._make_oauth2_stub()

        with patch.dict("os.environ", {"GOOGLE_SERVICE_ACCOUNT_PATH": "/no/such/file.json"}), \
             patch("os.path.exists", return_value=False), \
             patch("app.get_workspace_client", return_value=mock_ws_client), \
             patch.dict(sys.modules, {
                 "gspread": gspread_mod,
                 "oauth2client": types.ModuleType("oauth2client"),
                 "oauth2client.service_account": oauth2_mod,
             }):
            client = app._get_gsheets_client()

        mock_ws_client.workspace.export.assert_called_once_with(path="/no/such/file.json")
        oauth2_mod.ServiceAccountCredentials.from_json_keyfile_dict.assert_called_once()
        gspread_mod.authorize.assert_called_once_with(fake_creds)
        self.assertIsNotNone(client)

    def test_raises_when_neither_file_nor_workspace_works(self):
        gspread_mod = self._make_gspread_stub()
        oauth2_mod, _ = self._make_oauth2_stub()

        mock_ws_client = MagicMock()
        mock_ws_client.workspace.export.side_effect = RuntimeError("not found")

        with patch.dict("os.environ", {"GOOGLE_SERVICE_ACCOUNT_PATH": "/no/such/file.json"}), \
             patch("os.path.exists", return_value=False), \
             patch("app.get_workspace_client", return_value=mock_ws_client), \
             patch.dict(sys.modules, {
                 "gspread": gspread_mod,
                 "oauth2client": types.ModuleType("oauth2client"),
                 "oauth2client.service_account": oauth2_mod,
             }):
            with self.assertRaises(ValueError) as ctx:
                app._get_gsheets_client()

        self.assertIn("Could not load Google service account", str(ctx.exception))


# ---------------------------------------------------------------------------
# Google Sheets end-to-end: load tab data → _do_import
# ---------------------------------------------------------------------------

class TestGsheetsImportFlow(unittest.TestCase):
    """
    Simulates the full path a user follows in the Google Sheets tab:
      1. Parse the URL to get spreadsheet_id + gid
      2. Connect via _get_gsheets_client()
      3. Read all values from the selected worksheet
      4. Build a DataFrame and pass it to _do_import
    """

    def _build_gspread_stub(self, sheet_data):
        """Return a gspread client mock whose worksheet returns sheet_data."""
        ws_mock = MagicMock(name="worksheet")
        ws_mock.get_all_values.return_value = sheet_data
        ws_mock.id = 0
        ws_mock.title = "Sheet1"

        spreadsheet_mock = MagicMock(name="spreadsheet")
        spreadsheet_mock.worksheets.return_value = [ws_mock]
        spreadsheet_mock.get_worksheet_by_id.return_value = ws_mock

        client_mock = MagicMock(name="gspread_client")
        client_mock.open_by_key.return_value = spreadsheet_mock

        gspread_mod = types.ModuleType("gspread")
        gspread_mod.authorize = MagicMock(return_value=client_mock)
        return gspread_mod, client_mock, spreadsheet_mock, ws_mock

    def test_parse_url_then_read_worksheet(self):
        url = "https://docs.google.com/spreadsheets/d/SHEET_ID_123/edit#gid=0"
        sheet_data = [
            ["url", "team", "abuse_area"],
            ["https://t.me/channel1", "CT", "CSAM"],
            ["https://twitter.com/user1", "HS", "Extremism"],
        ]
        gspread_mod, client_mock, spreadsheet_mock, ws_mock = self._build_gspread_stub(sheet_data)
        oauth2_mod = types.ModuleType("oauth2client.service_account")
        oauth2_mod.ServiceAccountCredentials = MagicMock(
            from_json_keyfile_name=MagicMock(return_value=MagicMock()),
        )

        spreadsheet_id, gid = app._parse_gsheet_url(url)
        self.assertEqual(spreadsheet_id, "SHEET_ID_123")
        self.assertEqual(gid, 0)

        with patch("os.path.exists", return_value=True), \
             patch.dict(sys.modules, {
                 "gspread": gspread_mod,
                 "oauth2client": types.ModuleType("oauth2client"),
                 "oauth2client.service_account": oauth2_mod,
             }):
            gs_client = app._get_gsheets_client()

        spreadsheet = gs_client.open_by_key(spreadsheet_id)
        ws = spreadsheet.get_worksheet_by_id(gid)
        data = ws.get_all_values()

        raw_df = pd.DataFrame(data[1:], columns=data[0])
        self.assertEqual(len(raw_df), 2)
        self.assertIn("url", raw_df.columns)
        self.assertEqual(raw_df.iloc[0]["url"], "https://t.me/channel1")
        self.assertEqual(raw_df.iloc[1]["team"], "HS")

    def test_do_import_merges_rows_from_sheet(self):
        sheet_data = [
            ["url", "team", "notes"],
            ["https://t.me/channelA", "CT", "test note"],
            ["https://x.com/userB", "HS", ""],
            ["", "HS", "no url — should be skipped"],
        ]
        raw_df = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
        mapping = {"url": "url", "team": "team", "notes": "notes",
                   "abuse_area": None, "sub_abuse_area": None, "relevancy": None}

        executed_statements = []

        with patch("pages.import_sources.run_statement", side_effect=lambda sql: executed_statements.append(sql)), \
             patch("pages.import_sources.current_user", return_value="test_user"), \
             patch("pages.import_sources.load_sources", MagicMock()):
            imp._do_import(raw_df, mapping, platform_override="Auto-detect from URL",
                           col_hint_platform=None,
                           target_table="test.schema.test_sources")

        # Two valid rows → one bulk MERGE (UNION ALL) per batch
        merge_calls = [s for s in executed_statements if "MERGE INTO" in s]
        self.assertEqual(len(merge_calls), 1)

        # Both platforms present in the single bulk MERGE
        self.assertIn("Telegram", merge_calls[0])
        self.assertIn("Twitter/X", merge_calls[0])

        # User propagated into SQL
        self.assertIn("test_user", merge_calls[0])

    def test_do_import_platform_override(self):
        raw_df = pd.DataFrame({
            "url": ["https://t.me/ch1", "https://x.com/u1"],
            "team": ["CT", "CT"],
        })
        mapping = {"url": "url", "team": "team", "notes": None,
                   "abuse_area": None, "sub_abuse_area": None, "relevancy": None}

        executed_statements = []

        with patch("pages.import_sources.run_statement", side_effect=lambda sql: executed_statements.append(sql)), \
             patch("pages.import_sources.current_user", return_value="test_user"), \
             patch("pages.import_sources.load_sources", MagicMock()):
            imp._do_import(raw_df, mapping, platform_override="Telegram",
                           col_hint_platform=None,
                           target_table="test.schema.test_sources")

        merge_calls = [s for s in executed_statements if "MERGE INTO" in s]
        # Both rows in one bulk MERGE, all forced to Telegram
        self.assertEqual(len(merge_calls), 1)
        self.assertIn("Telegram", merge_calls[0])
        # Twitter/X must NOT appear
        self.assertNotIn("Twitter/X", merge_calls[0])

    def test_do_import_skips_all_empty_urls(self):
        raw_df = pd.DataFrame({"url": ["", None, "  "], "team": ["CT", "HS", "CS"]})
        mapping = {"url": "url", "team": "team", "notes": None,
                   "abuse_area": None, "sub_abuse_area": None, "relevancy": None}

        executed_statements = []
        with patch("pages.import_sources.run_statement", side_effect=lambda sql: executed_statements.append(sql)), \
             patch("pages.import_sources.current_user", return_value="u"), \
             patch("pages.import_sources.load_sources", MagicMock()):
            imp._do_import(raw_df, mapping, platform_override="Auto-detect from URL",
                           col_hint_platform=None,
                           target_table="test.schema.test_sources")

        merge_calls = [s for s in executed_statements if "MERGE INTO" in s]
        self.assertEqual(len(merge_calls), 0)

    def test_do_import_escapes_single_quotes_in_url(self):
        raw_df = pd.DataFrame({"url": ["https://t.me/it's_a_channel"], "team": ["CT"]})
        mapping = {"url": "url", "team": "team", "notes": None,
                   "abuse_area": None, "sub_abuse_area": None, "relevancy": None}

        executed_statements = []
        with patch("pages.import_sources.run_statement", side_effect=lambda sql: executed_statements.append(sql)), \
             patch("pages.import_sources.current_user", return_value="u"), \
             patch("pages.import_sources.load_sources", MagicMock()):
            imp._do_import(raw_df, mapping, platform_override="Telegram",
                           col_hint_platform=None,
                           target_table="test.schema.test_sources")

        merge_calls = [s for s in executed_statements if "MERGE INTO" in s]
        self.assertEqual(len(merge_calls), 1)
        # Single quote must be escaped, not raw
        self.assertNotIn("it's_a_channel", merge_calls[0])
        self.assertIn("it\\'s_a_channel", merge_calls[0])

    def test_do_import_col_hint_platform_fills_unknown(self):
        """When URL detection returns Unknown, col_hint_platform is used as fallback."""
        raw_df = pd.DataFrame({"telegram_url": ["https://example.com/unknownsite"], "team": ["CT"]})
        mapping = {"url": "telegram_url", "team": "team", "notes": None,
                   "abuse_area": None, "sub_abuse_area": None, "relevancy": None}

        executed_statements = []
        with patch("pages.import_sources.run_statement", side_effect=lambda sql: executed_statements.append(sql)), \
             patch("pages.import_sources.current_user", return_value="u"), \
             patch("pages.import_sources.load_sources", MagicMock()):
            imp._do_import(raw_df, mapping, platform_override="Auto-detect from URL",
                           col_hint_platform="Telegram",
                           target_table="test.schema.test_sources")

        merge_calls = [s for s in executed_statements if "MERGE INTO" in s]
        self.assertEqual(len(merge_calls), 1)
        self.assertIn("Telegram", merge_calls[0])

    def test_do_import_manual_values_used_when_column_not_mapped(self):
        """manual_values are injected into rows where the column was not mapped."""
        raw_df = pd.DataFrame({"url": ["https://t.me/ch1", "https://x.com/u1"]})
        mapping = {"url": "url", "team": None, "abuse_area": None,
                   "sub_abuse_area": None, "notes": None, "relevancy": None}
        manual_values = {"team": "CT", "abuse_area": "CSAM", "relevancy": "High"}

        executed_statements = []
        with patch("pages.import_sources.run_statement", side_effect=lambda sql: executed_statements.append(sql)), \
             patch("pages.import_sources.current_user", return_value="u"), \
             patch("pages.import_sources.load_sources", MagicMock()):
            imp._do_import(raw_df, mapping, platform_override="Auto-detect from URL",
                           col_hint_platform=None, manual_values=manual_values,
                           target_table="test.schema.test_sources")

        # Two rows → one bulk MERGE
        merge_calls = [s for s in executed_statements if "MERGE INTO" in s]
        self.assertEqual(len(merge_calls), 1)
        # Manual values appear in the merged SQL
        self.assertIn("CT", merge_calls[0])
        self.assertIn("CSAM", merge_calls[0])
        self.assertIn("High", merge_calls[0])

    def test_do_import_manual_values_not_overwrite_mapped_column(self):
        """A mapped column value takes precedence over manual_values for the same field."""
        raw_df = pd.DataFrame({"url": ["https://t.me/ch1"], "team": ["HS"]})
        mapping = {"url": "url", "team": "team", "abuse_area": None,
                   "sub_abuse_area": None, "notes": None, "relevancy": None}
        manual_values = {"team": "CT"}  # should NOT override the "HS" from the column

        executed_statements = []
        with patch("pages.import_sources.run_statement", side_effect=lambda sql: executed_statements.append(sql)), \
             patch("pages.import_sources.current_user", return_value="u"), \
             patch("pages.import_sources.load_sources", MagicMock()):
            imp._do_import(raw_df, mapping, platform_override="Telegram",
                           col_hint_platform=None, manual_values=manual_values,
                           target_table="test.schema.test_sources")

        merge_calls = [s for s in executed_statements if "MERGE INTO" in s]
        self.assertEqual(len(merge_calls), 1)
        stmt = merge_calls[0]
        # HS (from column) must appear; verify the team fragment specifically
        team_line = [l for l in stmt.splitlines() if "AS team" in l]
        self.assertTrue(any("HS" in l for l in team_line))


    def test_do_import_batches_large_input(self):
        """Rows exceeding _IMPORT_BATCH_SIZE are split into multiple MERGE calls."""
        n = imp._IMPORT_BATCH_SIZE + 10
        raw_df = pd.DataFrame({
            "url": [f"https://t.me/ch{i}" for i in range(n)],
        })
        mapping = {"url": "url", "team": None, "abuse_area": None,
                   "sub_abuse_area": None, "notes": None, "relevancy": None}

        executed_statements = []
        with patch("pages.import_sources.run_statement", side_effect=lambda sql: executed_statements.append(sql)), \
             patch("pages.import_sources.current_user", return_value="u"), \
             patch("pages.import_sources.load_sources", MagicMock()):
            imp._do_import(raw_df, mapping, platform_override="Telegram",
                           col_hint_platform=None,
                           target_table="test.schema.test_sources")

        merge_calls = [s for s in executed_statements if "MERGE INTO" in s]
        self.assertEqual(len(merge_calls), 2)  # one full batch + one remainder batch


if __name__ == "__main__":
    unittest.main()
