import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { createSyncConfig } from '../api/syncConfigs'
import { ErrorBanner } from '../components/shared/ErrorBanner'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input, Select, Textarea } from '../components/ui/Input'
import { IntervalPicker } from '../components/ui/IntervalPicker'
import { LoadingState } from '../components/ui/Spinner'
import { useToast } from '../components/ui/Toast'
import { useConfig } from '../contexts/ConfigContext'
import { useTeamContext } from '../contexts/TeamContext'

/* ── Types ─────────────────────────────────────────────────── */

interface ColumnMapping {
  url?: string
  team?: string
  abuse_area?: string
  sub_abuse_area?: string
  notes?: string
  relevancy?: string
}

interface ImportResult {
  imported: number
  skipped: number
  errors: string[]
  batches: number
}

interface SheetTab {
  id: number
  title: string
}


const FIELDS: (keyof ColumnMapping)[] = ['url', 'team', 'abuse_area', 'sub_abuse_area', 'notes', 'relevancy']
const FIELD_LABELS: Record<string, string> = {
  url: 'URL / Link *',
  team: 'Team',
  abuse_area: 'Abuse Area',
  sub_abuse_area: 'Sub Abuse Area',
  notes: 'Notes',
  relevancy: 'Relevancy',
}

/* ── Column auto-mapping ───────────────────────────────────── */

function autoMap(columns: string[]): ColumnMapping {
  const keywords: Record<string, string[]> = {
    url: ['url', 'link', 'account', 'channel', 'handle', 'profile'],
    team: ['team'],
    abuse_area: ['abuse area', 'abuse_area', 'classification', 'category', 'abuse'],
    sub_abuse_area: ['sub abuse', 'sub_abuse', 'subcategory', 'sub category'],
    notes: ['note', 'comment', 'description', 'remark'],
    relevancy: ['relevancy', 'relevance', 'relevant'],
  }
  const result: ColumnMapping = {}
  for (const [field, keys] of Object.entries(keywords)) {
    for (const col of columns) {
      if (keys.some((k) => col.toLowerCase().includes(k))) {
        ;(result as any)[field] = col
        break
      }
    }
  }
  return result
}

/* ── Shared import UI ──────────────────────────────────────── */

interface MappingProps {
  columns: string[]
  team: string
  platforms: string[]
  relevancyOptions: string[]
  allRows?: string[][]
  preview?: string[][]
  onImport: (
    mapping: ColumnMapping,
    platformOverride: string,
    manualValues: Record<string, string>,
    metaMapping: Record<string, string>,
    rowFilters: Record<string, string[]>,
  ) => void
  isPending?: boolean
}

function MappingAndImport({ columns, team, platforms, relevancyOptions, allRows, preview, onImport, isPending }: MappingProps) {
  const [mapping, setMapping] = useState<ColumnMapping>(() => autoMap(columns))
  const [platformOverride, setPlatformOverride] = useState('Auto-detect from URL')
  const [manualValues, setManualValues] = useState<Record<string, string>>({
    team: team,
    abuse_area: '',
    sub_abuse_area: '',
  })
  const [metaCols, setMetaCols] = useState<Set<string>>(new Set())
  const [rowFilters, setRowFilters] = useState<Record<string, Set<string>>>({})
  const [filterExpanded, setFilterExpanded] = useState<Record<string, boolean>>({})

  const dataRows = allRows ?? preview ?? []

  // Compute unique values per column
  const uniqueValues: Record<string, string[]> = {}
  for (let ci = 0; ci < columns.length; ci++) {
    const vals = new Set<string>()
    for (const row of dataRows) {
      const v = row[ci]
      if (v != null && v !== '') vals.add(v)
    }
    uniqueValues[columns[ci]] = Array.from(vals).sort()
  }

  // Filter rows for display
  const filteredRows = dataRows.filter((row) => {
    for (const [col, allowed] of Object.entries(rowFilters)) {
      if (allowed.size === 0) continue
      const ci = columns.indexOf(col)
      if (ci === -1) continue
      if (!allowed.has(row[ci])) return false
    }
    return true
  })

  const activeFilterCount = Object.values(rowFilters).filter((s) => s.size > 0).length
  const displayPreview = filteredRows.slice(0, 5)

  // Columns already assigned to standard fields
  const mappedCols = new Set(Object.values(mapping).filter(Boolean))
  // Remaining columns not mapped to standard fields
  const unmappedCols = columns.filter((c) => !mappedCols.has(c))

  function toggleMetaCol(col: string) {
    setMetaCols((prev) => {
      const next = new Set(prev)
      next.has(col) ? next.delete(col) : next.add(col)
      return next
    })
  }

  function toggleFilterValue(col: string, val: string) {
    setRowFilters((prev) => {
      const cur = prev[col] ?? new Set()
      const next = new Set(cur)
      next.has(val) ? next.delete(val) : next.add(val)
      return { ...prev, [col]: next }
    })
  }

  function handleImport() {
    const metaMapping: Record<string, string> = {}
    for (const col of metaCols) metaMapping[col] = col
    const filters: Record<string, string[]> = {}
    for (const [col, vals] of Object.entries(rowFilters)) {
      if (vals.size > 0) filters[col] = Array.from(vals)
    }
    onImport(mapping, platformOverride, manualValues, metaMapping, filters)
  }

  return (
    <div className="flex flex-col gap-4 mt-4">
      {/* Row Filters */}
      {dataRows.length > 0 && (
        <Card padding="md">
          <div className="card-header">
            <span className="card-title">
              Row Filters
              {activeFilterCount > 0 && (
                <span style={{ fontWeight: 400, fontSize: 12, color: 'var(--t-accent)', marginLeft: 8 }}>
                  {activeFilterCount} active — {filteredRows.length} of {dataRows.length} rows
                </span>
              )}
            </span>
          </div>
          <p className="text-sm text-muted mb-3">
            Optionally filter which rows to import by selecting allowed values per column.
          </p>
          <div className="flex flex-col gap-2">
            {columns.map((col) => {
              const uv = uniqueValues[col]
              if (!uv || uv.length <= 1) return null
              if (uv.length > 200) return null
              const expanded = filterExpanded[col]
              const selected = rowFilters[col] ?? new Set()
              return (
                <div key={col} style={{ border: '1px solid var(--border-2)', borderRadius: 'var(--r-md)', padding: '8px 12px' }}>
                  <button
                    type="button"
                    onClick={() => setFilterExpanded((p) => ({ ...p, [col]: !p[col] }))}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, width: '100%', padding: 0, color: 'var(--t1)', fontSize: 13, fontWeight: 500 }}
                  >
                    <span style={{ transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s', fontSize: 10 }}>&#9654;</span>
                    {col}
                    {selected.size > 0 && (
                      <span style={{ fontSize: 11, color: 'var(--t-accent)', fontWeight: 400 }}>
                        ({selected.size} selected)
                      </span>
                    )}
                    <span style={{ fontSize: 11, color: 'var(--t3)', fontWeight: 400, marginLeft: 'auto' }}>
                      {uv.length} values
                    </span>
                  </button>
                  {expanded && (
                    <div className="flex flex-wrap gap-1" style={{ marginTop: 8, maxHeight: 160, overflowY: 'auto' }}>
                      {uv.map((val) => (
                        <label
                          key={val}
                          className="flex items-center gap-1 text-sm"
                          style={{
                            padding: '3px 8px',
                            background: selected.has(val) ? 'var(--accent-dim)' : 'var(--surface-3)',
                            border: `1px solid ${selected.has(val) ? 'var(--accent-border)' : 'var(--border-2)'}`,
                            borderRadius: 'var(--r-sm)',
                            cursor: 'pointer',
                            color: selected.has(val) ? 'var(--t-accent)' : 'var(--t2)',
                            fontSize: 11,
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={selected.has(val)}
                            onChange={() => toggleFilterValue(col, val)}
                            style={{ width: 12, height: 12 }}
                          />
                          {val}
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {/* Data preview */}
      {displayPreview.length > 0 && (
        <Card padding="none">
          <div className="card-header" style={{ padding: '10px 14px 0' }}>
            <span className="card-title">
              Preview (first {displayPreview.length} of {filteredRows.length} rows)
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ fontSize: 11 }}>
              <thead>
                <tr>
                  {columns.map((c) => <th key={c} style={{ padding: '7px 10px' }}>{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {displayPreview.map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td key={ci} style={{ padding: '5px 10px', maxWidth: 160, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Column mapping */}
      <Card padding="md">
        <div className="card-header">
          <span className="card-title">Column Mapping</span>
        </div>
        <div className="grid-2 mb-4">
          {FIELDS.map((field) => (
            <Select
              key={field}
              label={FIELD_LABELS[field]}
              value={(mapping as any)[field] ?? ''}
              onChange={(e) => setMapping((m) => ({ ...m, [field]: e.target.value || undefined }))}
            >
              <option value="">— none —</option>
              {columns.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
          ))}
        </div>

        <div style={{ maxWidth: 280 }}>
          <Select
            label="Platform override"
            value={platformOverride}
            onChange={(e) => setPlatformOverride(e.target.value)}
          >
            <option value="Auto-detect from URL">Auto-detect from URL</option>
            {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
          </Select>
        </div>
      </Card>

      {/* Manual values (applied when no column is mapped) */}
      <Card padding="md">
        <div className="card-header">
          <span className="card-title">Manual Value Overrides</span>
        </div>
        <p className="text-sm text-muted mb-3">
          These values are applied to every imported row when the corresponding column is not mapped above.
        </p>
        <div className="grid-2">
          <Input
            label="Team"
            value={manualValues.team ?? ''}
            onChange={(e) => setManualValues((v) => ({ ...v, team: e.target.value }))}
            placeholder={team}
          />
          <Input
            label="Abuse Area"
            value={manualValues.abuse_area ?? ''}
            onChange={(e) => setManualValues((v) => ({ ...v, abuse_area: e.target.value }))}
            placeholder="e.g. Cybercrime"
          />
          <Input
            label="Sub Abuse Area"
            value={manualValues.sub_abuse_area ?? ''}
            onChange={(e) => setManualValues((v) => ({ ...v, sub_abuse_area: e.target.value }))}
            placeholder="e.g. Phishing"
          />
          <Select
            label="Relevancy"
            value={manualValues.relevancy ?? ''}
            onChange={(e) => setManualValues((v) => ({ ...v, relevancy: e.target.value }))}
          >
            <option value="">— none —</option>
            {relevancyOptions.map((r) => <option key={r} value={r}>{r}</option>)}
          </Select>
        </div>
      </Card>

      {/* Metadata column mapping */}
      {unmappedCols.length > 0 && (
        <Card padding="md">
          <div className="card-header">
            <span className="card-title">Additional Columns → Metadata JSON</span>
          </div>
          <p className="text-sm text-muted mb-3">
            Checked columns will be stored as JSON in the <code>metadata</code> field.
          </p>
          <div className="flex flex-wrap gap-2">
            {unmappedCols.map((col) => (
              <label
                key={col}
                className="flex items-center gap-2 text-sm"
                style={{
                  padding: '5px 10px',
                  background: metaCols.has(col) ? 'var(--accent-dim)' : 'var(--surface-3)',
                  border: `1px solid ${metaCols.has(col) ? 'var(--accent-border)' : 'var(--border-2)'}`,
                  borderRadius: 'var(--r-md)',
                  cursor: 'pointer',
                  color: metaCols.has(col) ? 'var(--t-accent)' : 'var(--t2)',
                  transition: 'all var(--ease)',
                }}
              >
                <input
                  type="checkbox"
                  checked={metaCols.has(col)}
                  onChange={() => toggleMetaCol(col)}
                  style={{ width: 13, height: 13 }}
                />
                {col}
              </label>
            ))}
          </div>
        </Card>
      )}

      {!mapping.url && (
        <p className="text-sm" style={{ color: 'var(--warning)' }}>
          Map the URL column to continue.
        </p>
      )}

      <div>
        <Button variant="primary" size="md" disabled={!mapping.url} loading={isPending} onClick={handleImport}>
          Import
        </Button>
      </div>
    </div>
  )
}

function ImportResultDisplay({ result }: { result: ImportResult }) {
  const hasErrors = result.errors.length > 0
  return (
    <div className={`mt-4 ${hasErrors ? 'import-result-warn' : 'import-result-ok'}`}>
      <p className="font-medium">
        {hasErrors
          ? `⚠ Completed with ${result.errors.length} error(s). ${result.imported} rows processed.`
          : `✓ Imported ${result.imported} rows in ${result.batches} batch(es). Skipped ${result.skipped} empty-URL rows.`}
      </p>
      {result.errors.map((e, i) => (
        <pre key={i} style={{ marginTop: 8, fontSize: 11 }}>{e}</pre>
      ))}
    </div>
  )
}

/* ── Page ──────────────────────────────────────────────────── */

export function ImportSources() {
  const { team } = useTeamContext()
  const { platforms, relevancy_options } = useConfig()
  const [searchParams] = useSearchParams()
  const initialTab = searchParams.get('tab') === 'gsheet' ? 'gsheet' : 'csv'
  const initialAutoSync = searchParams.get('autosync') === '1'
  const [tab, setTab] = useState<'csv' | 'paste' | 'gsheet'>(initialTab)

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Import Sources</h1>
        <p className="page-subtitle">Import into <strong style={{ color: 'var(--t-accent)' }}>{team}</strong></p>
      </div>

      <div className="tabs">
        {(['csv', 'paste', 'gsheet'] as const).map((t) => (
          <button key={t} className={`tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t === 'csv' ? 'Upload CSV' : t === 'paste' ? 'Paste Data' : 'Google Sheets'}
          </button>
        ))}
      </div>

      {tab === 'csv'    && <CsvTab    team={team} platforms={platforms} relevancyOptions={relevancy_options} />}
      {tab === 'paste'  && <PasteTab  team={team} platforms={platforms} relevancyOptions={relevancy_options} />}
      {tab === 'gsheet' && <GsheetTab team={team} platforms={platforms} relevancyOptions={relevancy_options} initialAutoSync={initialAutoSync} />}
    </div>
  )
}

/* ── CSV Tab ───────────────────────────────────────────────── */

function CsvTab({ team, platforms, relevancyOptions }: { team: string; platforms: string[]; relevancyOptions: string[] }) {
  const { addToast } = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [columns, setColumns] = useState<string[] | null>(null)
  const [allRows, setAllRows] = useState<string[][] | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)

  const importMutation = useMutation({
    mutationFn: async ({
      mapping,
      platformOverride,
      manualValues,
      metaMapping,
    }: {
      mapping: ColumnMapping
      platformOverride: string
      manualValues: Record<string, string>
      metaMapping: Record<string, string>
      rowFilters: Record<string, string[]>
    }) => {
      const fd = new FormData()
      fd.append('file', file!)
      fd.append('mapping_json', JSON.stringify(mapping))
      fd.append('platform_override', platformOverride)
      fd.append('manual_values_json', JSON.stringify(manualValues))
      fd.append('meta_mapping_json', JSON.stringify(metaMapping))
      fd.append('row_filters_json', JSON.stringify(rowFilters))
      const res = await api.post<ImportResult>(`/import/csv?team=${encodeURIComponent(team)}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data
    },
    onSuccess: (r) => {
      setResult(r)
      if (r.errors.length > 0) {
        addToast(`Import completed with ${r.errors.length} error(s). ${r.imported} rows processed.`, 'warning')
      } else {
        addToast(`Successfully imported ${r.imported} rows in ${r.batches} batch(es).`, 'success')
      }
    },
    onError: (e: Error) => {
      addToast(`Import failed: ${e.message}`, 'error')
    },
  })

  async function handleFile(f: File) {
    setFile(f)
    setResult(null)
    const text = await f.text()
    const lines = text.split('\n').filter((l) => l.trim())
    const header = lines[0]
    const cols = header.split(',').map((c) => c.trim().replace(/^"|"$/g, ''))
    setColumns(cols)

    const rows = lines.slice(1).map((line) =>
      line.split(',').map((c) => c.trim().replace(/^"|"$/g, ''))
    )
    setAllRows(rows)
  }

  return (
    <div>
      <label className="file-drop-area">
        <input type="file" accept=".csv" onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--t3)" strokeWidth="1.5" strokeLinecap="round">
          <path d="M12 4v12M8 8l4-4 4 4"/><path d="M4 18h16"/>
        </svg>
        <span className="file-drop-label">{file ? file.name : 'Click to choose a CSV file'}</span>
        <span className="file-drop-sub">CSV with headers in the first row</span>
      </label>

      <ErrorBanner error={importMutation.error} title="Import failed" />
      {columns && (
        <MappingAndImport
          columns={columns}
          team={team}
          platforms={platforms}
          relevancyOptions={relevancyOptions}
          allRows={allRows ?? undefined}
          isPending={importMutation.isPending}
          onImport={(mapping, po, mv, mm, rf) => importMutation.mutate({ mapping, platformOverride: po, manualValues: mv, metaMapping: mm, rowFilters: rf })}
        />
      )}
      {result && <ImportResultDisplay result={result} />}
    </div>
  )
}

/* ── Paste Tab ─────────────────────────────────────────────── */

function PasteTab({ team, platforms, relevancyOptions }: { team: string; platforms: string[]; relevancyOptions: string[] }) {
  const { addToast } = useToast()
  const [text, setText] = useState('')
  const [columns, setColumns] = useState<string[] | null>(null)
  const [allRows, setAllRows] = useState<string[][] | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)

  const importMutation = useMutation({
    mutationFn: async ({
      mapping,
      platformOverride,
      manualValues,
      metaMapping,
    }: {
      mapping: ColumnMapping
      platformOverride: string
      manualValues: Record<string, string>
      metaMapping: Record<string, string>
      rowFilters: Record<string, string[]>
    }) => {
      const res = await api.post<ImportResult>(`/import/paste?team=${encodeURIComponent(team)}`, {
        text,
        import_request: {
          mapping,
          platform_override: platformOverride,
          manual_values: manualValues,
          meta_mapping: metaMapping,
          row_filters: rowFilters,
        },
      })
      return res.data
    },
    onSuccess: (r) => {
      setResult(r)
      if (r.errors.length > 0) {
        addToast(`Import completed with ${r.errors.length} error(s). ${r.imported} rows processed.`, 'warning')
      } else {
        addToast(`Successfully imported ${r.imported} rows in ${r.batches} batch(es).`, 'success')
      }
    },
    onError: (e: Error) => {
      addToast(`Import failed: ${e.message}`, 'error')
    },
  })

  function parseCols() {
    const lines = text.split('\n').filter((l) => l.trim())
    const firstLine = lines[0]
    let sep = '\t'
    for (const s of ['\t', ',', ';']) {
      if (firstLine.split(s).length > 1) { sep = s; break }
    }
    const cols = firstLine.split(sep).map((c) => c.trim())
    setColumns(cols)
    setAllRows(
      lines.slice(1).map((l) => l.split(sep).map((c) => c.trim()))
    )
  }

  return (
    <div>
      <p className="text-sm text-muted mb-3">
        Paste tab-separated or CSV data. Include column headers in the first row.
      </p>
      <Textarea
        value={text}
        onChange={(e) => { setText(e.target.value); setColumns(null); setAllRows(null); setResult(null) }}
        rows={7}
        placeholder={"Column1\tColumn2\t...\nvalue1\tvalue2\t..."}
        className="w-full"
      />
      {text.trim() && !columns && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={parseCols}>
          Detect columns
        </Button>
      )}
      <ErrorBanner error={importMutation.error} title="Import failed" />
      {columns && (
        <MappingAndImport
          columns={columns}
          team={team}
          platforms={platforms}
          relevancyOptions={relevancyOptions}
          allRows={allRows ?? undefined}
          isPending={importMutation.isPending}
          onImport={(mapping, po, mv, mm, rf) => importMutation.mutate({ mapping, platformOverride: po, manualValues: mv, metaMapping: mm, rowFilters: rf })}
        />
      )}
      {result && <ImportResultDisplay result={result} />}
    </div>
  )
}

/* ── Google Sheets Tab ─────────────────────────────────────── */

function GsheetTab({ team, platforms, relevancyOptions, initialAutoSync }: { team: string; platforms: string[]; relevancyOptions: string[]; initialAutoSync?: boolean }) {
  const { addToast } = useToast()
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [tabs, setTabs] = useState<SheetTab[] | null>(null)
  const [selectedGid, setSelectedGid] = useState<number | ''>('')
  const [selectedTabTitle, setSelectedTabTitle] = useState('')
  const [columns, setColumns] = useState<string[] | null>(null)
  const [allRows, setAllRows] = useState<string[][] | null>(null)
  const [spreadsheetId, setSpreadsheetId] = useState('')
  const [spreadsheetName, setSpreadsheetName] = useState('')
  const [result, setResult] = useState<ImportResult | null>(null)
  const [tabsError, setTabsError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadingTab, setLoadingTab] = useState(false)
  const [importing, setImporting] = useState(false)
  const [enableAutoSync, setEnableAutoSync] = useState(initialAutoSync ?? false)
  const [syncInterval, setSyncInterval] = useState(1440)

  async function connectSheets() {
    setTabsError(null)
    setTabs(null)
    setColumns(null)
    setAllRows(null)
    setSelectedGid('')
    setSelectedTabTitle('')
    try {
      const res = await api.get<{ name: string; tabs: SheetTab[] }>('/import/gsheet/sheets', { params: { url } })
      setTabs(res.data.tabs)
      setSpreadsheetName(res.data.name)
      const m = url.match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/)
      if (m) setSpreadsheetId(m[1])
    } catch (e: any) {
      setTabsError(e.message)
    }
  }

  async function loadTab(gid: number) {
    setLoadError(null)
    setLoadingTab(true)
    setColumns(null)
    setAllRows(null)
    setResult(null)
    setSelectedGid(gid)
    const tab = tabs?.find((t) => t.id === gid)
    setSelectedTabTitle(tab?.title ?? '')
    try {
      const res = await api.get<{ columns: string[]; preview: string[][]; all_rows?: string[][] }>('/import/gsheet/columns', {
        params: { id: spreadsheetId, gid },
      })
      setColumns(res.data.columns)
      setAllRows(res.data.all_rows ?? res.data.preview)
    } catch (e: any) {
      setLoadError(e.message)
    } finally {
      setLoadingTab(false)
    }
  }

  async function doImport(
    mapping: ColumnMapping,
    platformOverride: string,
    manualValues: Record<string, string>,
    metaMapping: Record<string, string>,
    rowFilters: Record<string, string[]>,
  ) {
    setImporting(true)
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('spreadsheet_id', spreadsheetId)
      fd.append('gid', String(selectedGid))
      fd.append('mapping_json', JSON.stringify(mapping))
      fd.append('platform_override', platformOverride)
      fd.append('manual_values_json', JSON.stringify(manualValues))
      fd.append('meta_mapping_json', JSON.stringify(metaMapping))
      fd.append('row_filters_json', JSON.stringify(rowFilters))
      const res = await api.post<ImportResult>(`/import/gsheet/import?team=${encodeURIComponent(team)}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(res.data)
      if (res.data.errors.length > 0) {
        addToast(`Import completed with ${res.data.errors.length} error(s). ${res.data.imported} rows processed.`, 'warning')
      } else {
        addToast(`Successfully imported ${res.data.imported} rows in ${res.data.batches} batch(es).`, 'success')
      }
      if (enableAutoSync && spreadsheetId && selectedGid !== '') {
        try {
          await createSyncConfig(team, {
            spreadsheet_id: spreadsheetId,
            spreadsheet_url: url,
            spreadsheet_name: spreadsheetName,
            tab_title: selectedTabTitle,
            gid: selectedGid as number,
            team,
            mapping_json: JSON.stringify(mapping),
            platform_override: platformOverride,
            manual_values_json: JSON.stringify(manualValues),
            meta_mapping_json: JSON.stringify(metaMapping),
            sync_interval_minutes: syncInterval,
          })
          addToast('Auto-sync enabled — redirecting to Connected Sheets', 'success')
          setTimeout(() => navigate(`/${encodeURIComponent(team)}/connected-sheets`), 1500)
        } catch (e: any) {
          addToast(`Import succeeded but auto-sync setup failed: ${e.message}`, 'warning')
        }
      }
    } catch (e: any) {
      setLoadError(e.message)
      addToast(`Import failed: ${e.message}`, 'error')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div>
      <p className="text-sm text-muted mb-3">
        Enter a Google Sheets URL. The sheet must be shared with the service account.
      </p>

      <div className="flex gap-2 mb-4">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://docs.google.com/spreadsheets/d/..."
          className="form-input flex-1"
        />
        <Button variant="primary" size="md" onClick={connectSheets} disabled={!url.trim()}>
          Connect
        </Button>
      </div>

      {tabsError && <p className="text-danger text-sm mb-3">{tabsError}</p>}

      {/* Tab selector — dropdown */}
      {tabs && tabs.length > 0 && (
        <div style={{ maxWidth: 320, marginBottom: 16 }}>
          <Select
            label="Select tab"
            value={String(selectedGid)}
            onChange={(e) => {
              const gid = Number(e.target.value)
              if (!isNaN(gid) && e.target.value !== '') loadTab(gid)
            }}
          >
            <option value="">— choose a tab —</option>
            {tabs.map((t) => (
              <option key={t.id} value={t.id}>{t.title}</option>
            ))}
          </Select>
        </div>
      )}

      {loadingTab && <LoadingState text="Loading tab data…" />}
      {loadError && <p className="text-danger text-sm mb-3">{loadError}</p>}

      {columns && !loadingTab && (
        <>
          <MappingAndImport
            columns={columns}
            team={team}
            platforms={platforms}
            relevancyOptions={relevancyOptions}
            allRows={allRows ?? undefined}
            isPending={importing}
            onImport={doImport}
          />
          <Card padding="md" className="mt-4">
            <label className="flex items-center gap-3" style={{ cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={enableAutoSync}
                onChange={(e) => setEnableAutoSync(e.target.checked)}
                style={{ width: 16, height: 16 }}
              />
              <div>
                <span className="font-medium text-sm">Enable auto-sync for this sheet</span>
                <p className="text-xs text-muted" style={{ marginTop: 2 }}>
                  Automatically pull new rows from this tab on a recurring schedule
                </p>
              </div>
            </label>
            {enableAutoSync && (
              <div style={{ marginTop: 12, marginLeft: 28 }}>
                <IntervalPicker minutes={syncInterval} onChange={setSyncInterval} />
              </div>
            )}
          </Card>
        </>
      )}
      {result && <ImportResultDisplay result={result} />}
    </div>
  )
}
