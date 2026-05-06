import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import type { RunStatus } from '../api/jobs'
import { cancelRun, getJobDetails, getWorkflowConfig, triggerJob } from '../api/jobs'
import type { SheetTab } from '../api/gsheets'
import { getSheetData, listSheets, renameTab, updateSheet } from '../api/gsheets'
import { TaskGraph } from '../components/jobs/TaskGraph'
import { ErrorBanner } from '../components/shared/ErrorBanner'
import { Button } from '../components/ui/Button'
import { Card, CardHeader } from '../components/ui/Card'
import { LoadingState } from '../components/ui/Spinner'
import { useTeamContext } from '../contexts/TeamContext'
import { useJobMonitor } from '../hooks/useJobMonitor'

export function TelegramWorkflow() {
  const { team } = useTeamContext()

  const { data: config, isLoading: configLoading } = useQuery({
    queryKey: ['workflow-config', team],
    queryFn: () => getWorkflowConfig(team),
    staleTime: Infinity,
    enabled: !!team,
  })

  if (configLoading) return (
    <div className="page-container"><LoadingState /></div>
  )

  if (!config) return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Telegram Workflow</h1>
      </div>
      <p className="text-muted text-sm">
        No workflow configured for team <strong style={{ color: 'var(--t-accent)' }}>{team}</strong>.
      </p>
    </div>
  )

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Telegram Workflow</h1>
        <p className="page-subtitle">
          Team: <strong style={{ color: 'var(--t-accent)' }}>{team}</strong>
          {' · '}
          <a href={config.sheet_url} target="_blank" rel="noopener noreferrer">Spreadsheet ↗</a>
          {' · '}
          <a href={config.job_url} target="_blank" rel="noopener noreferrer">Databricks Job ↗</a>
        </p>
      </div>

      <div className="flex gap-6" style={{ alignItems: 'flex-start' }}>
        <div style={{ width: 320, flexShrink: 0 }}>
          <JobControl jobId={parseInt(config.job_id)} jobUrl={config.job_url} />
        </div>
        <div className="flex-1 min-w-0">
          <SpreadsheetPanel sheetId={config.sheet_id} sheetUrl={config.sheet_url} />
        </div>
      </div>
    </div>
  )
}

function JobControl({ jobId, jobUrl }: { jobId: number; jobUrl: string }) {
  const [activeRunId, setActiveRunId] = useState<number | null>(null)
  const { status, error: streamError } = useJobMonitor(activeRunId)

  const { data: jobDetail, isLoading } = useQuery({
    queryKey: ['job-detail', jobId],
    queryFn: () => getJobDetails(jobId),
    staleTime: 60_000,
  })

  useEffect(() => {
    if (jobDetail?.active_run_id && !activeRunId) {
      setActiveRunId(jobDetail.active_run_id)
    }
  }, [jobDetail?.active_run_id])

  const triggerMutation = useMutation({
    mutationFn: () => triggerJob(jobId),
    onSuccess: (r) => setActiveRunId(r.run_id),
  })

  const cancelMutation = useMutation({
    mutationFn: () => cancelRun(activeRunId!),
  })

  return (
    <Card padding="lg">
      <CardHeader title="Job Control" />

      {isLoading ? (
        <LoadingState text="Loading job info…" />
      ) : jobDetail ? (
        <div className="mb-4">
          <div className="font-medium" style={{ marginBottom: 2 }}>{jobDetail.name}</div>
          <div className="text-xs text-dim text-mono">
            Last run: {jobDetail.last_run_at?.slice(0, 16) ?? 'Never'}
          </div>
        </div>
      ) : null}

      <ErrorBanner error={streamError} title="Stream error" />
      <ErrorBanner error={triggerMutation.error} title="Trigger failed" />

      {status ? (
        <RunStatusView
          status={status}
          onStopTracking={() => setActiveRunId(null)}
          onCancel={() => cancelMutation.mutate()}
          onClear={() => setActiveRunId(null)}
          jobUrl={`${jobUrl}/runs/${activeRunId}`}
        />
      ) : activeRunId ? (
        <LoadingState text="Connecting to run stream…" />
      ) : (
        <Button
          variant="primary"
          size="md"
          loading={triggerMutation.isPending}
          onClick={() => triggerMutation.mutate()}
        >
          Run Now
        </Button>
      )}
    </Card>
  )
}

function RunStatusView({
  status, onStopTracking, onCancel, onClear, jobUrl,
}: {
  status: RunStatus
  onStopTracking: () => void
  onCancel: () => void
  onClear: () => void
  jobUrl: string
}) {
  const elapsed = status.elapsed_seconds != null ? ` · ${status.elapsed_seconds}s` : ''

  if (status.is_running) {
    return (
      <div>
        <div className="run-status-box run-status-running">
          <strong>{status.life_cycle}</strong>{elapsed}
        </div>
        <a href={jobUrl} target="_blank" rel="noopener noreferrer" className="text-sm text-accent" style={{ display: 'block', marginBottom: 10 }}>
          View in Databricks ↗
        </a>
        <TaskGraph tasks={status.tasks} />
        <div className="flex gap-2 mt-3">
          <Button variant="ghost" size="sm" onClick={onStopTracking}>Stop tracking</Button>
          <Button variant="danger" size="sm" onClick={onCancel}>⏹ Stop job</Button>
        </div>
        <p className="text-xs text-dim mt-2">Polling every 15s</p>
      </div>
    )
  }

  const success = status.result === 'SUCCESS'
  return (
    <div>
      <div className={`run-status-box ${success ? 'run-status-success' : 'run-status-failed'}`}>
        {success ? '✓ Completed successfully' : `✗ ${status.result || status.life_cycle}${status.message ? ` — ${status.message}` : ''}`}
        {' · '}
        <a href={jobUrl} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'underline', fontSize: 12 }}>
          View run ↗
        </a>
      </div>
      <TaskGraph tasks={status.tasks} />
      <Button variant="secondary" size="sm" className="mt-3" onClick={onClear}>
        Clear &amp; run again
      </Button>
    </div>
  )
}

function SpreadsheetPanel({ sheetId, sheetUrl }: { sheetId: string; sheetUrl: string }) {
  const [selectedGid, setSelectedGid] = useState<number | null>(null)

  const { data: tabs, isLoading: tabsLoading, error: tabsError } = useQuery({
    queryKey: ['sheet-tabs', sheetId],
    queryFn: () => listSheets(sheetUrl),
    staleTime: 60_000,
  })

  useEffect(() => {
    if (tabs && tabs.length > 0 && selectedGid === null) {
      setSelectedGid(tabs[0].id)
    }
  }, [tabs])

  const { data: sheetData, isLoading: dataLoading } = useQuery({
    queryKey: ['sheet-data', sheetId, selectedGid],
    queryFn: () => getSheetData(sheetId, selectedGid!),
    enabled: selectedGid !== null,
    staleTime: 30_000,
  })

  const [editedRows, setEditedRows] = useState<string[][] | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [newTabName, setNewTabName] = useState('')
  const [saveMsg, setSaveMsg] = useState('')

  const saveMutation = useMutation({
    mutationFn: () => {
      const tab = (tabs as SheetTab[]).find((t) => t.id === selectedGid)!
      const rows = [sheetData!.columns, ...(editedRows ?? sheetData!.rows)]
      return updateSheet({ sheet_id: sheetId, tab_title: tab.title, rows })
    },
    onSuccess: () => setSaveMsg('Saved!'),
  })

  const renameMutation = useMutation({
    mutationFn: () => {
      const tab = (tabs as SheetTab[]).find((t) => t.id === selectedGid)!
      return renameTab({ sheet_id: sheetId, old_title: tab.title, new_title: newTabName })
    },
    onSuccess: () => setRenaming(false),
  })

  const activeTab = (tabs as SheetTab[] | undefined)?.find((t) => t.id === selectedGid)

  return (
    <Card padding="lg">
      <CardHeader title="Spreadsheet" />

      <ErrorBanner error={tabsError} title="Sheet error" />

      {tabsLoading ? (
        <LoadingState text="Loading tabs…" />
      ) : Array.isArray(tabs) && tabs.length > 0 ? (
        <>
          <div className="flex flex-wrap gap-2 mb-4">
            {(tabs as SheetTab[]).map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setSelectedGid(tab.id); setEditedRows(null); setSaveMsg('') }}
                className={`btn btn-sm ${selectedGid === tab.id ? 'btn-accent' : 'btn-secondary'}`}
                style={selectedGid === tab.id ? { background: 'var(--accent-dim)', color: 'var(--t-accent)', borderColor: 'var(--accent-border)' } : undefined}
              >
                {tab.title}
              </button>
            ))}
            <button
              onClick={() => { setRenaming(!renaming); setNewTabName(activeTab?.title ?? '') }}
              className="btn btn-xs btn-ghost"
            >
              Rename tab
            </button>
          </div>

          {renaming && (
            <div className="flex gap-2 mb-4">
              <input
                value={newTabName}
                onChange={(e) => setNewTabName(e.target.value)}
                className="form-input"
                style={{ maxWidth: 200 }}
              />
              <Button variant="primary" size="sm" loading={renameMutation.isPending} onClick={() => renameMutation.mutate()}>
                Save
              </Button>
            </div>
          )}
        </>
      ) : null}

      {dataLoading ? (
        <LoadingState text="Loading data…" />
      ) : sheetData ? (
        <>
          <div className="table-wrap mb-4" style={{ maxHeight: 400, overflowY: 'auto' }}>
            <table className="sheet-table">
              <thead>
                <tr>
                  {sheetData.columns.map((col, i) => (
                    <th key={i}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(editedRows ?? sheetData.rows).map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td key={ci}>
                        <input
                          value={cell}
                          onChange={(e) => {
                            const rows = (editedRows ?? sheetData.rows.map((r) => [...r]))
                            rows[ri][ci] = e.target.value
                            setEditedRows([...rows])
                          }}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="primary"
              size="sm"
              loading={saveMutation.isPending}
              onClick={() => { saveMutation.mutate(); setSaveMsg('') }}
            >
              Save changes to sheet
            </Button>
            {saveMsg && <span className="text-sm text-success">{saveMsg}</span>}
          </div>
        </>
      ) : null}
    </Card>
  )
}
