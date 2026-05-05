import io
import json
import uuid

import pandas as pd
import streamlit as st

def _app():
    import app as _a
    return _a

_IMPORT_BATCH_SIZE = 500

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_IMPORT_FIELD_KEYWORDS = {
    "url":           ["url", "link", "account", "channel", "handle", "profile"],
    "team":          ["team"],
    "abuse_area":    ["abuse area", "abuse_area", "classification", "category", "abuse"],
    "sub_abuse_area":["sub abuse", "sub_abuse", "subcategory", "sub category"],
    "notes":         ["note", "comment", "description", "remark"],
    "relevancy":     ["relevancy", "relevance", "relevant"],
}

_IMPORT_FIELD_LABELS = {
    "url":           "URL / Link column *",
    "team":          "Team column",
    "abuse_area":    "Abuse Area column",
    "sub_abuse_area":"Sub Abuse Area column",
    "notes":         "Notes column",
    "relevancy":     "Relevancy column",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auto_map(columns: list) -> dict:
    mapping = {f: None for f in _IMPORT_FIELD_KEYWORDS}
    for field, keywords in _IMPORT_FIELD_KEYWORDS.items():
        for col in columns:
            if any(k in col.lower() for k in keywords):
                mapping[field] = col
                break
    return mapping


def _parse_paste(text: str) -> pd.DataFrame | None:
    for sep in ("\t", ",", ";"):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep)
            if len(df.columns) > 1:
                return df
        except Exception:
            pass
    return None


def _safe_val(row, col):
    if not col:
        return ""
    v = str(row.get(col, "") or "")
    return "" if v.lower() in ("nan", "none") else v


# ---------------------------------------------------------------------------
# Import UI
# ---------------------------------------------------------------------------

def _render_import_ui(raw_df: pd.DataFrame):
    a = _app()
    PLATFORMS = a.PLATFORMS
    RELEVANCY_OPTIONS = a.RELEVANCY_OPTIONS
    detect_platform_from_column_name = a.detect_platform_from_column_name
    detect_platform_from_url = a.detect_platform_from_url
    get_selected_team = a.get_selected_team
    get_sources_table = a.get_sources_table
    team = get_selected_team()
    target_table = get_sources_table()
    st.info(f"Importing into **{team}** table (`{target_table}`)")

    st.subheader("Column Mapping")
    cols_with_none = [None] + list(raw_df.columns)
    auto = _auto_map(list(raw_df.columns))

    def default_idx(field):
        val = auto.get(field)
        return cols_with_none.index(val) if val and val in cols_with_none else 0

    left, right = st.columns(2)
    mapping = {}
    with left:
        for field in ["url", "team", "abuse_area"]:
            mapping[field] = st.selectbox(
                _IMPORT_FIELD_LABELS[field], cols_with_none, index=default_idx(field)
            )
    with right:
        for field in ["sub_abuse_area", "notes", "relevancy"]:
            mapping[field] = st.selectbox(
                _IMPORT_FIELD_LABELS[field], cols_with_none, index=default_idx(field)
            )

    if not mapping["url"]:
        st.warning("Select the URL column to continue.")
        return

    col_hint_platform = detect_platform_from_column_name(mapping["url"])
    platform_options = ["Auto-detect from URL"] + PLATFORMS
    default_plat_idx = (
        platform_options.index(col_hint_platform)
        if col_hint_platform and col_hint_platform in platform_options
        else 0
    )

    platform_override = st.selectbox(
        "Platform override",
        platform_options,
        index=default_plat_idx,
        help="Auto-detect reads platform from each URL. Or force a single platform for all rows.",
    )
    if col_hint_platform and platform_override == "Auto-detect from URL":
        st.caption(f"Column name suggests platform: **{col_hint_platform}**")

    # Manual values — always shown; used as fallback when a row's mapped column is empty
    manual_values = {"team": team}
    st.subheader("Manual Values")
    st.caption("These values apply to every imported row where the column was not found (or is empty) in the spreadsheet.")
    m_left, m_right = st.columns(2)
    with m_left:
        manual_values["team"] = st.text_input("Team (manual)", value=team, key="manual_team")
        manual_values["abuse_area"] = st.text_input("Abuse Area (manual)", key="manual_abuse_area")
    with m_right:
        manual_values["sub_abuse_area"] = st.text_input("Sub Abuse Area (manual)", key="manual_sub_abuse_area")
        manual_values["relevancy"] = st.selectbox(
            "Relevancy (manual)", [""] + RELEVANCY_OPTIONS, key="manual_relevancy"
        )
    if not mapping.get("notes"):
        manual_values["notes"] = st.text_input("Notes (manual)", key="manual_notes")

    # Metadata field mapping
    st.subheader("Metadata Fields")
    st.caption("Map additional source columns to metadata fields stored as JSON on each source.")
    already_mapped = {v for v in mapping.values() if v}
    remaining_cols = [c for c in raw_df.columns if c not in already_mapped]
    if remaining_cols:
        meta_init = pd.DataFrame({
            "Include": [False] * len(remaining_cols),
            "Source Column": remaining_cols,
            "Metadata Field Name": remaining_cols,
        })
        meta_edited = st.data_editor(
            meta_init,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Include": st.column_config.CheckboxColumn(required=True),
                "Source Column": st.column_config.TextColumn(disabled=True),
                "Metadata Field Name": st.column_config.TextColumn(),
            },
        )
        meta_mapping = {
            row["Metadata Field Name"].strip(): row["Source Column"]
            for _, row in meta_edited[meta_edited["Include"] == True].iterrows()
            if row["Metadata Field Name"].strip()
        }
    else:
        st.caption("All columns are already mapped to standard fields.")
        meta_mapping = {}

    # Preview
    preview = []
    for _, row in raw_df.head(5).iterrows():
        url_val = _safe_val(row, mapping["url"])
        if platform_override == "Auto-detect from URL":
            plat = detect_platform_from_url(url_val) if url_val else ""
            if plat == "Unknown" and col_hint_platform:
                plat = col_hint_platform
        else:
            plat = platform_override
        meta_dict = {k: _safe_val(row, v) for k, v in meta_mapping.items() if _safe_val(row, v)}

        def _preview_val(field):
            v = _safe_val(row, mapping[field])
            if not v:
                v = manual_values.get(field, "")
            return v

        preview.append({
            "url": url_val,
            "platform": plat,
            "team": _preview_val("team"),
            "abuse_area": _preview_val("abuse_area"),
            "sub_abuse_area": _preview_val("sub_abuse_area"),
            "notes": _preview_val("notes"),
            "relevancy": _preview_val("relevancy"),
            "metadata": json.dumps(meta_dict) if meta_dict else "{}",
        })

    st.subheader(f"Preview — first {len(preview)} of {len(raw_df)} rows")
    st.dataframe(pd.DataFrame(preview), use_container_width=True)

    if st.button(f"Import {len(raw_df)} rows into {team}", type="primary"):
        _do_import(raw_df, mapping, platform_override, col_hint_platform, meta_mapping,
                   manual_values, target_table)


def _do_import(raw_df, mapping, platform_override, col_hint_platform,
               meta_mapping=None, manual_values=None, target_table=None):
    a = _app()
    detect_platform_from_url = a.detect_platform_from_url
    run_statement = a.run_statement
    load_sources = a.load_sources
    meta_mapping = meta_mapping or {}
    manual_values = manual_values or {}
    if target_table is None:
        target_table = a.get_sources_table()
    user = a.current_user().replace("'", "\\'")

    # Build SQL SELECT fragments for each valid row up-front
    row_selects = []
    skipped = 0

    for _, row in raw_df.iterrows():
        url_val = _safe_val(row, mapping["url"]).strip()
        if not url_val:
            skipped += 1
            continue

        if platform_override == "Auto-detect from URL":
            plat = detect_platform_from_url(url_val)
            if plat == "Unknown" and col_hint_platform:
                plat = col_hint_platform
        else:
            plat = platform_override

        def sv(field, _row=row):
            v = _safe_val(_row, mapping.get(field))
            if not v:
                v = manual_values.get(field, "")
            return v.replace("'", "\\'")

        meta_dict = {k: _safe_val(row, v) for k, v in meta_mapping.items() if _safe_val(row, v)}
        meta_json = json.dumps(meta_dict).replace("'", "\\'")
        new_id = str(uuid.uuid4())
        url_esc = url_val.replace("'", "\\'")
        plat_esc = plat.replace("'", "\\'")

        row_selects.append(
            f"SELECT '{new_id}' AS id, '{url_esc}' AS url, '{plat_esc}' AS platform,"
            f" '{sv('team')}' AS team, '{sv('abuse_area')}' AS abuse_area,"
            f" '{sv('sub_abuse_area')}' AS sub_abuse_area, '{sv('notes')}' AS notes,"
            f" '{sv('relevancy')}' AS relevancy, '{meta_json}' AS metadata,"
            f" current_timestamp() AS added_at, '{user}' AS added_by"
        )

    progress = st.progress(0, text="Importing…")

    if not row_selects:
        progress.empty()
        st.warning(f"No valid rows to import. Skipped {skipped} empty-URL rows.")
        return

    errors = []
    total = len(row_selects)

    for batch_start in range(0, total, _IMPORT_BATCH_SIZE):
        batch = row_selects[batch_start: batch_start + _IMPORT_BATCH_SIZE]
        union_sql = "\nUNION ALL\n".join(batch)
        try:
            run_statement(f"""
                MERGE INTO {target_table} AS t
                USING ({union_sql}) AS src
                ON t.url = src.url
                WHEN NOT MATCHED THEN INSERT *
            """)
        except Exception as e:
            batch_num = batch_start // _IMPORT_BATCH_SIZE + 1
            errors.append(f"Batch {batch_num}: {e}")

        done = min(batch_start + _IMPORT_BATCH_SIZE, total)
        progress.progress(done / total, text=f"Importing… {done}/{total}")

    progress.empty()

    if errors:
        st.warning(f"Completed with {len(errors)} batch error(s). {total} rows processed, {skipped} skipped.")
        with st.expander(f"{len(errors)} errors"):
            for e in errors:
                st.text(e)
    else:
        n_batches = (total + _IMPORT_BATCH_SIZE - 1) // _IMPORT_BATCH_SIZE
        st.success(f"Imported {total} rows in {n_batches} batch(es). Skipped {skipped} empty-URL rows.")

    load_sources.clear()


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

def page_import_sources():
    st.title("Import Sources")

    tab_upload, tab_paste, tab_gsheet = st.tabs(["Upload CSV", "Paste Spreadsheet", "Google Sheets Link"])

    with tab_upload:
        uploaded = st.file_uploader("Upload a CSV file", type=["csv"])
        if uploaded:
            try:
                raw_df = pd.read_csv(uploaded)
                st.caption(f"{len(raw_df)} rows · {len(raw_df.columns)} columns")
                _render_import_ui(raw_df)
            except Exception as e:
                st.error(f"Could not parse file: {e}")

    with tab_paste:
        st.caption(
            "Paste tab-separated or CSV data from your spreadsheet. "
            "Include column headers in the first row."
        )
        pasted = st.text_area(
            "Paste data here",
            height=200,
            placeholder="Column1\tColumn2\t...\nvalue1\tvalue2\t...",
        )
        if pasted.strip():
            raw_df = _parse_paste(pasted)
            if raw_df is None or raw_df.empty:
                st.error("Could not parse the pasted data. Ensure it has headers and is tab-, comma-, or semicolon-separated.")
            else:
                st.caption(f"{len(raw_df)} rows · {len(raw_df.columns)} columns")
                _render_import_ui(raw_df)

    with tab_gsheet:
        from app import _get_gsheets_client, _parse_gsheet_url

        st.caption(
            "Enter a Google Sheets URL. The sheet must be shared with the service account. "
            "If no tab is pre-selected in the URL, you can choose one after connecting."
        )
        gsheet_url = st.text_input(
            "Google Sheets URL",
            placeholder="https://docs.google.com/spreadsheets/d/.../.../edit#gid=0",
        )

        if gsheet_url.strip():
            try:
                spreadsheet_id, url_gid = _parse_gsheet_url(gsheet_url.strip())
            except ValueError as e:
                st.error(str(e))
                return

            if st.button("Connect & List Sheets"):
                try:
                    client = _get_gsheets_client()
                    spreadsheet = client.open_by_key(spreadsheet_id)
                    sheets = spreadsheet.worksheets()
                    st.session_state["gsheet_sheets"] = [(ws.id, ws.title) for ws in sheets]
                    st.session_state["gsheet_spreadsheet_id"] = spreadsheet_id
                    st.session_state["gsheet_url_gid"] = url_gid
                    st.session_state.pop("gsheet_df", None)
                except Exception as e:
                    st.error(f"Could not connect: {e}")

            if "gsheet_sheets" in st.session_state and st.session_state.get("gsheet_spreadsheet_id") == spreadsheet_id:
                sheets = st.session_state["gsheet_sheets"]
                url_gid = st.session_state.get("gsheet_url_gid")

                sheet_labels = [title for _, title in sheets]
                default_idx = next(
                    (i for i, (gid, _) in enumerate(sheets) if gid == url_gid), 0
                )
                selected_label = st.selectbox("Select tab", sheet_labels, index=default_idx)
                selected_gid = next(gid for gid, title in sheets if title == selected_label)

                if st.button("Load Tab"):
                    try:
                        client = _get_gsheets_client()
                        ws = client.open_by_key(spreadsheet_id).get_worksheet_by_id(selected_gid)
                        data = ws.get_all_values()
                        if not data:
                            st.warning("Sheet is empty.")
                        else:
                            raw_df = pd.DataFrame(data[1:], columns=data[0])
                            st.session_state["gsheet_df"] = raw_df
                    except Exception as e:
                        st.error(f"Could not load tab: {e}")

                if "gsheet_df" in st.session_state:
                    raw_df = st.session_state["gsheet_df"]
                    st.caption(f"{len(raw_df)} rows · {len(raw_df.columns)} columns")
                    _render_import_ui(raw_df)
