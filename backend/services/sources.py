import uuid
from datetime import datetime, timedelta

import pandas as pd

from backend.config import STAGING_TABLE, get_sources_table
from backend.services.databricks_client import current_user, run_query, run_statement


def load_sources(table: str) -> pd.DataFrame:
    return run_query(f"SELECT * FROM {table} ORDER BY added_at DESC")


def _esc(v: str) -> str:
    return str(v).replace("'", "\\'")


def _like_any(col: str, values: list[str]) -> str:
    """Match rows where a comma-separated column contains any of the given values."""
    parts = [f"{col} LIKE '%{_esc(v)}%'" for v in values if v]
    if not parts:
        return "TRUE"
    return f"({' OR '.join(parts)})"


def _in_clause(col: str, values: list[str]) -> str:
    """Return `col = 'x'` or `col IN ('x','y',...)` for the given values list."""
    escaped = [f"'{_esc(v)}'" for v in values if v]
    if not escaped:
        return "TRUE"
    if len(escaped) == 1:
        return f"{col} = {escaped[0]}"
    return f"{col} IN ({', '.join(escaped)})"


def build_filter_where(
    platform: list[str] | None = None,
    keyword: str | None = None,
    abuse_area: list[str] | None = None,
    sub_abuse_area: list[str] | None = None,
    relevancy: list[str] | None = None,
    added_by: list[str] | None = None,
) -> str:
    """Return SQL WHERE clause body (no WHERE keyword) for the given filters.

    Categorical params accept a list of values and generate IN clauses.
    """
    conditions: list[str] = []
    if platform:
        conditions.append(_in_clause("platform", platform))
    if keyword:
        k = _esc(keyword)
        conditions.append(
            f"(url LIKE '%{k}%' OR COALESCE(notes, '') LIKE '%{k}%'"
            f" OR COALESCE(platform, '') LIKE '%{k}%'"
            f" OR COALESCE(abuse_area, '') LIKE '%{k}%'"
            f" OR COALESCE(sub_abuse_area, '') LIKE '%{k}%'"
            f" OR COALESCE(relevancy, '') LIKE '%{k}%'"
            f" OR COALESCE(added_by, '') LIKE '%{k}%'"
            f" OR COALESCE(metadata, '') LIKE '%{k}%')"
        )
    if abuse_area:
        conditions.append(_like_any("abuse_area", abuse_area))
    if sub_abuse_area:
        conditions.append(_like_any("sub_abuse_area", sub_abuse_area))
    if relevancy:
        conditions.append(_in_clause("relevancy", relevancy))
    if added_by:
        conditions.append(_in_clause("added_by", added_by))
    return " AND ".join(conditions) if conditions else "TRUE"


def count_sources_filtered(table: str, where: str) -> int:
    df = run_query(f"SELECT COUNT(*) AS cnt FROM {table} WHERE {where}")
    return int(df["cnt"].iloc[0]) if not df.empty else 0


def load_sources_page(table: str, where: str, limit: int, offset: int) -> pd.DataFrame:
    return run_query(
        f"SELECT * FROM {table} WHERE {where} ORDER BY added_at DESC LIMIT {limit} OFFSET {offset}"
    )


def get_filter_options(table: str) -> dict:
    """Return distinct non-empty values for categorical filter dropdowns."""
    def distinct(col: str) -> list[str]:
        df = run_query(
            f"SELECT DISTINCT {col} FROM {table} "
            f"WHERE {col} IS NOT NULL AND {col} != '' ORDER BY {col}"
        )
        return df[col].tolist() if not df.empty else []

    def distinct_split(col: str) -> list[str]:
        """Like distinct() but splits comma-separated values and deduplicates."""
        raw = distinct(col)
        seen: set[str] = set()
        result: list[str] = []
        for val in raw:
            for part in val.split(","):
                part = part.strip()
                if part and part not in seen:
                    seen.add(part)
                    result.append(part)
        result.sort()
        return result

    return {
        "platforms":       distinct("platform"),
        "abuse_areas":     distinct_split("abuse_area"),
        "sub_abuse_areas": distinct_split("sub_abuse_area"),
        "relevancies":     distinct("relevancy"),
        "added_by":        distinct("added_by"),
    }


def wipe_all_sources(table: str) -> int:
    df = run_query(f"SELECT COUNT(*) AS cnt FROM {table}")
    count = int(df["cnt"].iloc[0]) if not df.empty else 0
    if count > 0:
        run_statement(f"DELETE FROM {table} WHERE TRUE")
    return count


def delete_sources_by_ids(table: str, ids: list[str]) -> None:
    escaped = ", ".join(f"'{i.replace(chr(39), chr(39)*2)}'" for i in ids)
    run_statement(f"DELETE FROM {table} WHERE id IN ({escaped})")


def insert_source(
    table: str,
    url: str,
    platform: str,
    team: str,
    abuse_area: str = "",
    sub_abuse_area: str = "",
    notes: str = "",
    relevancy: str = "",
    user: str | None = None,
) -> None:
    new_id = str(uuid.uuid4())
    if user is None:
        user = current_user()

    def s(v: str) -> str:
        return str(v or "").replace("'", "\\'")

    run_statement(f"""
        INSERT INTO {table}
          (id, url, platform, team, abuse_area, sub_abuse_area,
           notes, relevancy, metadata, added_at, added_by)
        VALUES
          ('{new_id}', '{s(url)}', '{s(platform)}',
           '{s(team)}', '{s(abuse_area)}', '{s(sub_abuse_area)}',
           '{s(notes)}', '{s(relevancy)}', '{{}}',
           current_timestamp(), '{s(user)}')
    """)


def get_multivalue_options(df: pd.DataFrame, column: str) -> list:
    values: set[str] = set()
    for val in df[column].dropna():
        for v in str(val).split(","):
            v = v.strip()
            if v:
                values.add(v)
    return sorted(values)


def multivalue_mask(series: pd.Series, selected: list) -> pd.Series:
    selected_set = set(selected)

    def matches(val: object) -> bool:
        if pd.isna(val) or not str(val).strip():
            return False
        return bool({v.strip() for v in str(val).split(",")} & selected_set)

    return series.apply(matches)


def get_dashboard_data(table: str) -> dict:
    df = load_sources(table)
    if df.empty:
        return {
            "total_sources": 0,
            "added_this_week": 0,
            "platforms_count": 0,
            "by_platform": {},
            "by_relevancy": {},
            "daily_counts": [],
        }

    total = len(df)
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    added_this_week = int(len(df[df["added_at"].astype(str) >= cutoff])) if "added_at" in df.columns else 0
    platforms_count = int(df["platform"].nunique())

    by_platform = df.groupby("platform").size().to_dict()
    by_platform = {str(k): int(v) for k, v in by_platform.items()}

    rel = df[df["relevancy"].notna() & (df["relevancy"] != "")]
    by_relevancy = rel.groupby("relevancy").size().to_dict() if not rel.empty else {}
    by_relevancy = {str(k): int(v) for k, v in by_relevancy.items()}

    daily_counts: list[dict] = []
    if "added_at" in df.columns:
        df["added_date"] = pd.to_datetime(df["added_at"]).dt.date
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).date()
        daily = df[df["added_date"] >= cutoff_date].groupby("added_date").size()
        daily_counts = [{"date": str(d), "count": int(c)} for d, c in daily.items()]

    return {
        "total_sources": total,
        "added_this_week": added_this_week,
        "platforms_count": platforms_count,
        "by_platform": by_platform,
        "by_relevancy": by_relevancy,
        "daily_counts": daily_counts,
    }
