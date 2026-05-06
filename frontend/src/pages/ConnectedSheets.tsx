import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { SyncConfig } from '../api/syncConfigs'
import { createSyncConfig, deleteSyncConfig, listSyncConfigs, triggerSync, updateSyncConfig } from '../api/syncConfigs'
import { ErrorBanner } from '../components/shared/ErrorBanner'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input, Select } from '../components/ui/Input'
import { IntervalPicker } from '../components/ui/IntervalPicker'
import { LoadingState } from '../components/ui/Spinner'
import { useToast } from '../components/ui/Toast'
import { useConfig } from '../contexts/ConfigContext'
import { useTeamContext } from '../contexts/TeamContext'

function formatInterval(m: number): string {
  if (m >= 43200 && m % 43200 === 0) return `${m / 43200} month${m / 43200 > 1 ? 's' : ''}`
  if (m >= 10080 && m % 10080 === 0) return `${m / 10080} week${m / 10080 > 1 ? 's' : ''}`
  if (m >= 1440 && m % 1440 === 0) return `${m / 1440} day${m / 1440 > 1 ? 's' : ''}`
  if (m >= 60 && m % 60 === 0) return `${m / 60} hour${m / 60 > 1 ? 's' : ''}`
  return `${m} min`
}

interface SheetTab { id: number; title: string }

interface ColumnMapping {
  url?: string
  team?: string
  abuse_area?: string
  sub_abuse_area?: string
  notes?: string
  relevancy?: string
}

const FIELD_LABELS: Record<string, string> = {
  url: 'URL / Link *',
  team: 'Team',
  abuse_area: 'Abuse Area',
  sub_abuse_area: 'Sub Abuse Area',
  notes: 'Notes',
  relevancy: 'Relevancy',
}

export function ConnectedSheets() {
  const { team } = useTeamContext()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: configs, isLoading, error } = useQuery({
    queryKey: ['sync-configs', team],
    queryFn: () => listSyncConfigs(team),
    staleTime: 30_000,
  })

  const [editId, setEditId] = useState<string | null>(null)

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="page-title">Connected Spreadsheets</h1>
            <p className="page-subtitle">
              Auto-sync sources from Google Sheets into <strong style={{ color: 'var(--t-accent)' }}>{team}</strong>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => qc.invalidateQueries({ queryKey: ['sync-configs', team] })}>
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M1 8a7 7 0 0 1 13-3.5M15 8a7 7 0 0 1-13 3.5"/><path d="M14 1v4h-4M2 15v-4h4"/>
              </svg>
              Refresh
            </Button>
            <Button variant="primary" size="md" onClick={() => navigate(`/${encodeURIComponent(team)}/import?tab=gsheet&autosync=1`)}>
              + Connect Sheet
            </Button>
          </div>
        </div>
      </div>

      <ErrorBanner error={error} title="Failed to load sync configs" />

      {isLoading ? (
        <LoadingState text="Loading connected sheets..." />
      ) : !configs?.length ? (
        <div className="empty-state">
          <svg className="empty-icon" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="4" y="6" width="32" height="28" rx="3"/>
            <path d="M4 14h32M14 14v20M26 14v20"/>
          </svg>
          <p className="empty-text">No connected spreadsheets</p>
          <p className="empty-sub">Connect a Google Sheet to automatically pull new sources</p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {configs.map((cfg) => (
            <SyncConfigCard
              key={cfg.id}
              config={cfg}
              isEditing={editId === cfg.id}
              onEdit={() => setEditId(editId === cfg.id ? null : cfg.id)}
              onRefresh={() => qc.invalidateQueries({ queryKey: ['sync-configs', team] })}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Sync Config Card ──────────────────────────────────────── */

function SyncConfigCard({
  config,
  isEditing,
  onEdit,
  onRefresh,
}: {
  config: SyncConfig
  isEditing: boolean
  onEdit: () => void
  onRefresh: () => void
}) {
  const { addToast } = useToast()
  const [confirmDelete, setConfirmDelete] = useState(false)

  const toggleMutation = useMutation({
    mutationFn: () => updateSyncConfig(config.id, { sync_enabled: !config.sync_enabled }),
    onSuccess: () => { onRefresh(); addToast(config.sync_enabled ? 'Sync paused' : 'Sync enabled', 'info') },
  })

  const syncNowMutation = useMutation({
    mutationFn: () => triggerSync(config.id),
    onSuccess: (r) => {
      onRefresh()
      if (r.errors.length) {
        addToast(`Sync completed with ${r.errors.length} error(s)`, 'warning')
      } else {
        addToast(`Synced ${r.imported} rows`, 'success')
      }
    },
    onError: (e: Error) => addToast(`Sync failed: ${e.message}`, 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteSyncConfig(config.id),
    onSuccess: () => { onRefresh(); addToast('Connection removed', 'info') },
  })

  const lastSync = config.last_sync_at ? config.last_sync_at.slice(0, 19).replace('T', ' ') : 'Never'

  return (
    <Card padding="md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3" style={{ minWidth: 0 }}>
          <Badge variant={config.sync_enabled ? 'success' : 'neutral'} size="sm">
            {config.sync_enabled ? 'Active' : 'Paused'}
          </Badge>
          <a
            href={config.spreadsheet_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium truncate"
            style={{ maxWidth: 400 }}
          >
            {config.spreadsheet_name}
          </a>
          <span className="text-dim text-xs">/ {config.tab_title}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="xs"
            onClick={() => toggleMutation.mutate()}
            loading={toggleMutation.isPending}
          >
            {config.sync_enabled ? 'Pause' : 'Enable'}
          </Button>
          <Button
            variant="secondary"
            size="xs"
            onClick={() => syncNowMutation.mutate()}
            loading={syncNowMutation.isPending}
          >
            Sync Now
          </Button>
          <Button variant="ghost" size="xs" onClick={onEdit}>
            {isEditing ? 'Close' : 'Edit'}
          </Button>
          {!confirmDelete ? (
            <Button variant="ghost" size="xs" onClick={() => setConfirmDelete(true)}>Remove</Button>
          ) : (
            <div className="flex items-center gap-2">
              <Button variant="danger" size="xs" onClick={() => deleteMutation.mutate()} loading={deleteMutation.isPending}>Confirm</Button>
              <Button variant="ghost" size="xs" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-6 text-xs text-muted">
        <span>Interval: <strong>{formatInterval(config.sync_interval_minutes)}</strong></span>
        <span>Last sync: <strong>{lastSync}</strong></span>
        {config.last_sync_rows != null && config.last_sync_rows > 0 && (
          <span>Rows: <strong>{config.last_sync_rows}</strong></span>
        )}
        <span>Platform: <strong>{config.platform_override}</strong></span>
      </div>

      {config.last_sync_error && (
        <div className="mt-3 text-xs" style={{ color: 'var(--danger)' }}>
          Last error: {config.last_sync_error}
        </div>
      )}

      {isEditing && (
        <EditMappingForm config={config} onSaved={onRefresh} />
      )}
    </Card>
  )
}

/* ── Edit Mapping Form ─────────────────────────────────────── */

function EditMappingForm({ config, onSaved }: { config: SyncConfig; onSaved: () => void }) {
  const { platforms, relevancy_options } = useConfig()
  const { addToast } = useToast()

  const [mapping, setMapping] = useState<ColumnMapping>(() => {
    try { return JSON.parse(config.mapping_json || '{}') } catch { return {} }
  })
  const [platformOverride, setPlatformOverride] = useState(config.platform_override)
  const [manualValues, setManualValues] = useState<Record<string, string>>(() => {
    try { return JSON.parse(config.manual_values_json || '{}') } catch { return {} }
  })
  const [interval, setInterval_] = useState(config.sync_interval_minutes)
  const [columns, setColumns] = useState<string[] | null>(null)
  const [loadingCols, setLoadingCols] = useState(false)

  async function loadColumns() {
    setLoadingCols(true)
    try {
      const res = await api.get<{ columns: string[] }>('/import/gsheet/columns', {
        params: { id: config.spreadsheet_id, gid: config.gid },
      })
      setColumns(res.data.columns)
    } catch {
      addToast('Failed to load columns from sheet', 'error')
    } finally {
      setLoadingCols(false)
    }
  }

  const saveMutation = useMutation({
    mutationFn: () => updateSyncConfig(config.id, {
      mapping_json: JSON.stringify(mapping),
      platform_override: platformOverride,
      manual_values_json: JSON.stringify(manualValues),
      sync_interval_minutes: interval,
    }),
    onSuccess: () => { onSaved(); addToast('Settings saved', 'success') },
    onError: (e: Error) => addToast(`Save failed: ${e.message}`, 'error'),
  })

  return (
    <div className="mt-4" style={{ borderTop: '1px solid var(--border-0)', paddingTop: 16 }}>
      <div className="flex items-center justify-between mb-3">
        <span className="card-title">Column Mapping & Settings</span>
        {!columns && (
          <Button variant="ghost" size="xs" onClick={loadColumns} loading={loadingCols}>
            Load columns from sheet
          </Button>
        )}
      </div>

      <div className="grid-2 mb-4">
        {(Object.keys(FIELD_LABELS) as (keyof ColumnMapping)[]).map((field) => (
          <div key={field} className="form-field">
            <label className="form-label">{FIELD_LABELS[field]}</label>
            {columns ? (
              <select
                className="form-select"
                value={(mapping as any)[field] ?? ''}
                onChange={(e) => setMapping((m) => ({ ...m, [field]: e.target.value || undefined }))}
              >
                <option value="">— none —</option>
                {columns.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            ) : (
              <input
                className="form-input"
                value={(mapping as any)[field] ?? ''}
                onChange={(e) => setMapping((m) => ({ ...m, [field]: e.target.value || undefined }))}
                placeholder="Column name"
              />
            )}
          </div>
        ))}
      </div>

      <div className="grid-2 mb-4">
        <Select
          label="Platform override"
          value={platformOverride}
          onChange={(e) => setPlatformOverride(e.target.value)}
        >
          <option value="Auto-detect from URL">Auto-detect from URL</option>
          {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
        </Select>
        <IntervalPicker minutes={interval} onChange={setInterval_} />
      </div>

      <div className="grid-2 mb-4">
        <Input
          label="Manual Team"
          value={manualValues.team ?? ''}
          onChange={(e) => setManualValues((v) => ({ ...v, team: e.target.value }))}
        />
        <Input
          label="Manual Abuse Area"
          value={manualValues.abuse_area ?? ''}
          onChange={(e) => setManualValues((v) => ({ ...v, abuse_area: e.target.value }))}
        />
        <Input
          label="Manual Sub Abuse Area"
          value={manualValues.sub_abuse_area ?? ''}
          onChange={(e) => setManualValues((v) => ({ ...v, sub_abuse_area: e.target.value }))}
        />
        <Select
          label="Manual Relevancy"
          value={manualValues.relevancy ?? ''}
          onChange={(e) => setManualValues((v) => ({ ...v, relevancy: e.target.value }))}
        >
          <option value="">— none —</option>
          {relevancy_options.map((r) => <option key={r} value={r}>{r}</option>)}
        </Select>
      </div>

      <Button variant="primary" size="sm" onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
        Save Settings
      </Button>
    </div>
  )
}

/* ── Add New Sync Config ───────────────────────────────────── */

function AddSyncConfig({
  team,
  onDone,
  onCancel,
}: {
  team: string
  onDone: () => void
  onCancel: () => void
}) {
  const { platforms, relevancy_options } = useConfig()
  const { addToast } = useToast()

  const [url, setUrl] = useState('')
  const [tabs, setTabs] = useState<SheetTab[] | null>(null)
  const [selectedGid, setSelectedGid] = useState<number | ''>('')
  const [selectedTab, setSelectedTab] = useState('')
  const [spreadsheetId, setSpreadsheetId] = useState('')
  const [sheetName, setSheetName] = useState('')
  const [columns, setColumns] = useState<string[] | null>(null)
  const [mapping, setMapping] = useState<ColumnMapping>({})
  const [platformOverride, setPlatformOverride] = useState('Auto-detect from URL')
  const [manualValues, setManualValues] = useState<Record<string, string>>({ team })
  const [interval, setInterval_] = useState(30)
  const [connecting, setConnecting] = useState(false)
  const [loadingTab, setLoadingTab] = useState(false)

  async function connectSheet() {
    setConnecting(true)
    try {
      const res = await api.get<{ name: string; tabs: SheetTab[] }>('/import/gsheet/sheets', { params: { url } })
      setTabs(res.data.tabs)
      const m = url.match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/)
      if (m) setSpreadsheetId(m[1])
      setSheetName(res.data.name)
    } catch (e: any) {
      addToast(`Failed to connect: ${e.message}`, 'error')
    } finally {
      setConnecting(false)
    }
  }

  async function loadTab(gid: number) {
    setLoadingTab(true)
    setSelectedGid(gid)
    const tab = tabs?.find((t) => t.id === gid)
    setSelectedTab(tab?.title ?? '')
    try {
      const res = await api.get<{ columns: string[] }>('/import/gsheet/columns', {
        params: { id: spreadsheetId, gid },
      })
      setColumns(res.data.columns)
      // Auto-map
      const kw: Record<string, string[]> = {
        url: ['url', 'link', 'account', 'channel', 'handle', 'profile'],
        team: ['team'],
        abuse_area: ['abuse area', 'abuse_area', 'classification', 'category', 'abuse'],
        sub_abuse_area: ['sub abuse', 'sub_abuse', 'subcategory'],
        notes: ['note', 'comment', 'description'],
        relevancy: ['relevancy', 'relevance', 'relevant'],
      }
      const autoMapped: ColumnMapping = {}
      for (const [field, keys] of Object.entries(kw)) {
        for (const col of res.data.columns) {
          if (keys.some((k) => col.toLowerCase().includes(k))) {
            ;(autoMapped as any)[field] = col
            break
          }
        }
      }
      setMapping(autoMapped)
    } catch (e: any) {
      addToast(`Failed to load tab: ${e.message}`, 'error')
    } finally {
      setLoadingTab(false)
    }
  }

  const createMutation = useMutation({
    mutationFn: () => createSyncConfig(team, {
      spreadsheet_id: spreadsheetId,
      spreadsheet_url: url,
      spreadsheet_name: sheetName,
      tab_title: selectedTab,
      gid: selectedGid as number,
      team,
      mapping_json: JSON.stringify(mapping),
      platform_override: platformOverride,
      manual_values_json: JSON.stringify(manualValues),
      sync_interval_minutes: interval,
    }),
    onSuccess: () => { addToast('Sheet connected successfully', 'success'); onDone() },
    onError: (e: Error) => addToast(`Failed: ${e.message}`, 'error'),
  })

  return (
    <Card padding="md" className="mb-4">
      <div className="card-header">
        <span className="card-title">Connect a Google Sheet</span>
        <Button variant="ghost" size="xs" onClick={onCancel}>Cancel</Button>
      </div>

      <div className="flex gap-2 mb-4">
        <input
          className="form-input flex-1"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://docs.google.com/spreadsheets/d/..."
        />
        <Button variant="primary" size="md" onClick={connectSheet} disabled={!url.trim()} loading={connecting}>
          Connect
        </Button>
      </div>

      {tabs && (
        <div className="mb-4">
          <Input
            label="Sheet name (display)"
            value={sheetName}
            onChange={(e) => setSheetName(e.target.value)}
            placeholder="My Spreadsheet"
          />
        </div>
      )}

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
            {tabs.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
          </Select>
        </div>
      )}

      {loadingTab && <LoadingState text="Loading tab columns..." />}

      {columns && !loadingTab && (
        <>
          <div className="grid-2 mb-4">
            {(Object.keys(FIELD_LABELS) as (keyof ColumnMapping)[]).map((field) => (
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

          <div className="grid-2 mb-4">
            <Select
              label="Platform override"
              value={platformOverride}
              onChange={(e) => setPlatformOverride(e.target.value)}
            >
              <option value="Auto-detect from URL">Auto-detect from URL</option>
              {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
            <IntervalPicker minutes={interval} onChange={setInterval_} />
          </div>

          <div className="grid-2 mb-4">
            <Input
              label="Manual Team"
              value={manualValues.team ?? ''}
              onChange={(e) => setManualValues((v) => ({ ...v, team: e.target.value }))}
            />
            <Input
              label="Manual Abuse Area"
              value={manualValues.abuse_area ?? ''}
              onChange={(e) => setManualValues((v) => ({ ...v, abuse_area: e.target.value }))}
            />
            <Input
              label="Manual Sub Abuse Area"
              value={manualValues.sub_abuse_area ?? ''}
              onChange={(e) => setManualValues((v) => ({ ...v, sub_abuse_area: e.target.value }))}
            />
            <Select
              label="Manual Relevancy"
              value={manualValues.relevancy ?? ''}
              onChange={(e) => setManualValues((v) => ({ ...v, relevancy: e.target.value }))}
            >
              <option value="">— none —</option>
              {relevancy_options.map((r) => <option key={r} value={r}>{r}</option>)}
            </Select>
          </div>

          {!mapping.url && (
            <p className="text-sm mb-3" style={{ color: 'var(--warning)' }}>
              Map the URL column to continue.
            </p>
          )}

          <Button
            variant="primary"
            size="md"
            disabled={!mapping.url}
            loading={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            Save & Enable Auto-Sync
          </Button>
        </>
      )}
    </Card>
  )
}
