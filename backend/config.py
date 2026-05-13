import os
from functools import lru_cache

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


_TABLE_SUFFIX = os.environ.get("TABLE_SUFFIX", "")
TABLE_SUFFIX = _TABLE_SUFFIX
_SCHEMA = "af_delivery_dev.data_collection"

TEAMS: dict[str, str] = {
    "Child Safety":       f"social_sources_child_safety{_TABLE_SUFFIX}",
    "Human Exploitation": f"social_sources_human_exploitation{_TABLE_SUFFIX}",
    "Hate Speech":        f"social_sources_hate_speech{_TABLE_SUFFIX}",
    "NCII":               f"social_sources_ncii{_TABLE_SUFFIX}",
    "Illegal Goods":      f"social_sources_illegal_goods{_TABLE_SUFFIX}",
    "TEST":               f"social_sources_test{_TABLE_SUFFIX}",
}

STAGING_TABLE = f"{_SCHEMA}.social_sources_staging{_TABLE_SUFFIX}"
SYNC_CONFIG_TABLE = f"{_SCHEMA}.gsheet_sync_config{_TABLE_SUFFIX}"

# Pipelines
PIPELINE_RUNS_TABLE = f"{_SCHEMA}.pipeline_runs{_TABLE_SUFFIX}"
PIPELINE_RESULTS_GOOGLE_DORKING_TABLE = f"{_SCHEMA}.pipeline_results_google_dorking{_TABLE_SUFFIX}"
GOOGLE_DORKING_JOB_ID = int(os.environ.get("GOOGLE_DORKING_JOB_ID", 0))

PLATFORMS = ["Telegram", "Twitter/X", "TikTok", "Instagram", "YouTube", "Facebook", "Other"]
RELEVANCY_OPTIONS = ["Yes", "No", "Low", "Medium", "High", "True", "False"]

_PLATFORM_URL_PATTERNS: dict[str, list[str]] = {
    "Telegram":  ["t.me", "telegram.me", "telegram.org", "telemetr.io"],
    "Twitter/X": ["twitter.com/", "x.com/"],
    "TikTok":    ["tiktok.com/"],
    "Instagram": ["instagram.com/", "instagr.am/"],
    "YouTube":   ["youtube.com/", "youtu.be/"],
    "Facebook":  ["facebook.com/", "fb.com/", "fb.watch/"],
}

_PLATFORM_COL_KEYWORDS: dict[str, list[str]] = {
    "Telegram":  ["telegram"],
    "Twitter/X": ["twitter", "x.com", "tweet"],
    "TikTok":    ["tiktok", "tik tok"],
    "Instagram": ["instagram", "insta"],
    "YouTube":   ["youtube"],
    "Facebook":  ["facebook"],
}

_GOOGLE_SA_DEFAULT_PATH = (
    "/Workspace/Users/nikital@activefence.com/Upload to gsheet files/best-gsaccount-5b4811cedbed.json"
)
_GOOGLE_SA_CREDS_FOLDER = "/Workspace/Users/nikital@activefence.com/Upload to gsheet files"

WORKFLOW_CONFIG: dict[str, dict] = {
    "TEST": {
        "job_id":    "1013154753319258",
        "sheet_id":  "1q6xjR1zFhf5WOL8qaS6yiwu4mhD-DL45xCNklf_SpOU",
        "job_url":   "https://dbc-34ec8d98-3f7f.cloud.databricks.com/jobs/1013154753319258",
        "sheet_url": "https://docs.google.com/spreadsheets/d/1q6xjR1zFhf5WOL8qaS6yiwu4mhD-DL45xCNklf_SpOU/edit",
    },
}


def get_sources_table(team: str) -> str:
    table = TEAMS.get(team)
    if not table:
        raise ValueError(f"Unknown team: {team!r}")
    return f"{_SCHEMA}.{table}"


def detect_platform_from_url(url: str) -> str:
    if not url:
        return "Unknown"
    url_lower = url.lower()
    for platform, patterns in _PLATFORM_URL_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            return platform
    return "Unknown"


def detect_platform_from_column_name(col: str) -> str | None:
    col_lower = col.lower()
    for platform, keywords in _PLATFORM_COL_KEYWORDS.items():
        if any(k in col_lower for k in keywords):
            return platform
    return None
