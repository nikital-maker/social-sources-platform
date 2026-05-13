# Social Sources Platform — User Guide

This guide covers the three main sections of the platform: **Sources Browser**, **Import Sources**, and **Connected Sheets**.

---

## Getting Started

When you open the platform, you'll see a sidebar on the left. Before doing anything, **select your team** from the dropdown at the top of the sidebar. Your team determines which set of sources you're working with.

---

## Sources Browser

The Sources Browser is where you view, search, and manage all sources that have been added to your team's collection.

### Filtering Sources

At the top of the page you'll find several filter dropdowns:

- **Platform** — filter by source type (Telegram, Twitter, TikTok, etc.)
- **Abuse Area** — filter by abuse category
- **Sub Abuse Area** — filter by sub-category
- **Relevancy** — filter by relevancy level
- **Added By** — filter by who added the source
- **Search** — free-text keyword search across all fields

Each dropdown supports **multiple selections**. Selected values appear as small badges that you can remove by clicking the **×** next to them. When no value is selected, the filter shows "All" (meaning no filtering is applied).

To remove all active filters at once, click the **Clear** button.

### Refreshing Data

Click the **Refresh** button to reload the latest data from the database.

### Exporting to CSV

Click the **Export CSV** button to download all sources (matching your current filters) as a CSV file.

### Browsing the Table

The table displays your sources with these columns:

| Column | Description |
|---|---|
| **URL** | Clickable link to the source |
| **Platform** | Source type (shown as a colored badge) |
| **Abuse Area** | Abuse categories (comma-separated badges) |
| **Sub Area** | Sub-categories |
| **Relevancy** | Priority level (color-coded: red = high, yellow = medium) |
| **Notes** | Any notes attached to the source |
| **Metadata** | Extra fields stored as JSON — click to expand |
| **Added** | Date the source was added |
| **By** | Who added the source |

Use the **page controls** at the bottom to navigate through results.

### Deleting Sources

1. Check the boxes next to the sources you want to remove.
2. A counter shows how many rows you've selected.
3. Click **Delete selected**.
4. Confirm the deletion when prompted.

> Deletion is permanent and cannot be undone.

---

## Import Sources

The Import page lets you bring new sources into the platform. There are three ways to import, each available as a tab at the top of the page.

### Option 1: Upload CSV

1. Click the file drop area (or drag a CSV file onto it).
2. Your CSV must have **column headers in the first row**.

#### Row Filters (optional)

After selecting a file, a **Row Filters** panel appears. This lets you choose which rows to import by checking/unchecking values in each column. For example, you can import only rows where the "Platform" column is "Telegram". A badge shows how many rows will be imported out of the total.

#### Column Mapping

Map your CSV columns to the platform's fields:

- **URL / Link** (required) — the column containing source URLs
- **Team** — which team this source belongs to
- **Abuse Area** — abuse category
- **Sub Abuse Area** — sub-category
- **Notes** — any notes
- **Relevancy** — priority level
- **Platform override** — set to "Auto-detect from URL" to let the platform determine the source type automatically, or select a specific platform to apply to all rows

#### Manual Value Overrides

If your CSV doesn't have a column for a particular field (e.g., Abuse Area), you can type a value here and it will be applied to **every imported row**.

#### Additional Columns as Metadata

If your CSV has extra columns that weren't mapped above, you can check them here to store their values in the **metadata** field (as structured JSON data).

#### Running the Import

Click **Import** once your mapping is ready. You'll see a result message showing how many rows were imported and whether any were skipped or had errors.

### Option 2: Paste Data

1. Switch to the **Paste Data** tab.
2. Paste tab-separated or CSV-formatted data into the text area. Include column headers in the first row.
3. Click **Detect Columns**.
4. The same mapping and import options as the CSV tab appear.

### Option 3: Google Sheets

1. Switch to the **Google Sheets** tab.
2. Paste the full URL of a Google Spreadsheet.
3. Click **Connect**.
4. Select which **tab** (worksheet) to import from.
5. Map columns and set overrides as with CSV import.

#### Setting Up Auto-Sync

At the bottom of the Google Sheets import, you can enable **auto-sync**:

1. Check **"Enable auto-sync for this sheet"**.
2. Set the sync interval (e.g., every 1 day, every 6 hours).
3. Complete the import.

The platform will then automatically pull new rows from this sheet on the schedule you set. The sync configuration will appear on the **Connected Sheets** page.

---

## Connected Sheets

This page manages all Google Sheets that are set up for automatic syncing.

### Viewing Connected Sheets

Each connected sheet is shown as a card displaying:

- **Status badge** — "Active" (green) or "Paused"
- **Spreadsheet name** — clickable link that opens the sheet in Google Sheets
- **Tab name** — which worksheet tab is being synced
- **Sync interval** — how often new rows are pulled (e.g., "Every 1 day")
- **Last sync** — when the last sync occurred
- **Rows** — how many rows were pulled in the last sync
- **Platform** — the platform override, if set

If the last sync encountered an error, it will be shown in red text on the card.

### Managing a Connected Sheet

Each card has action buttons:

| Button | What it does |
|---|---|
| **Pause** / **Enable** | Temporarily stop or resume automatic syncing |
| **Sync Now** | Trigger an immediate sync without waiting for the next scheduled run |
| **Edit** | Open the settings form to change column mapping, sync interval, platform override, or manual values |
| **Remove** | Disconnect this sheet (asks for confirmation) |

### Editing Settings

Click **Edit** on a card to change:

- **Column mapping** — which spreadsheet columns map to which platform fields. Click **"Load columns from sheet"** to refresh the list of available columns.
- **Platform override** — auto-detect or a specific platform
- **Sync interval** — how often to pull new rows
- **Manual values** — default values for Team, Abuse Area, Sub Abuse Area, and Relevancy

Click **Save Settings** when done.

### Connecting a New Sheet

Click the **+ Connect Sheet** button in the top-right corner. This takes you to the Import page with the Google Sheets tab and auto-sync pre-selected.

---

## Tips

- **Duplicate handling** — The platform automatically prevents duplicate URLs. If a URL already exists in your team's collection, it won't be added again.
- **Platform auto-detection** — When set to "Auto-detect from URL", the platform recognizes Telegram (`t.me`, `telemetr.io`), Twitter/X, TikTok, and other platforms from the URL.
- **Switching teams** — Use the team dropdown in the sidebar. All pages update to show data for the selected team.
- **Refresh after changes** — After importing or syncing, click **Refresh** on the Sources Browser to see newly added sources.
