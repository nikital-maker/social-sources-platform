import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTeamContext } from '../contexts/TeamContext'
import { deletePipelineRun, listPipelineRuns } from '../api/pipelines'
import { Spinner } from '../components/ui/Spinner'
import { PipelineResults } from '../components/pipelines/PipelineResults'

const STATUS_BADGE: Record<string, string> = {
  pending: 'badge-neutral',
  running: 'badge-warning',
  completed: 'badge-success',
  failed: 'badge-danger',
}

export function PipelineRunHistory() {
  const { team } = useTeamContext()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)

  const { data: runsPage, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['pipeline-runs', team],
    queryFn: () => listPipelineRuns(team),
    refetchInterval: (query) => {
      const hasActive = query.state.data?.items.some(
        (r) => r.status === 'pending' || r.status === 'running'
      )
      return hasActive ? 5000 : false
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (runId: string) => deletePipelineRun(runId),
    onSuccess: (_data, runId) => {
      queryClient.removeQueries({ queryKey: ['pipeline-results', runId] })
      queryClient.invalidateQueries({ queryKey: ['pipeline-runs', team] })
      if (expandedRunId === runId) setExpandedRunId(null)
      setConfirmDeleteId(null)
    },
  })

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Pipeline Run History</h1>
          <p className="page-subtitle">All runs for <strong>{team}</strong></p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            {isFetching ? <><Spinner size="sm" /> Refreshing…</> : '↻ Refresh'}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => navigate(`/${encodeURIComponent(team)}/pipelines`)}
          >
            ← Back to Pipelines
          </button>
        </div>
      </div>

      <div className="card card-none">
        <div className="card-header card-sm" style={{ borderBottom: '1px solid var(--border-1)' }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Runs</span>
          {runsPage && (
            <span style={{ fontSize: 12, color: 'var(--t3)' }}>{runsPage.total} total</span>
          )}
        </div>

        {isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spinner /></div>
        ) : !runsPage || runsPage.items.length === 0 ? (
          <div style={{ padding: '32px 20px', color: 'var(--t3)', fontSize: 13, textAlign: 'center' }}>
            No pipeline runs yet.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Status</th>
                <th>Keywords</th>
                <th>Results</th>
                <th>Started</th>
                <th>By</th>
                <th>Error</th>
                <th style={{ width: 120 }}></th>
              </tr>
            </thead>
            <tbody>
              {runsPage.items.map((run) => {
                let keywords: string[] = []
                try { keywords = JSON.parse(run.config_json).keywords ?? [] } catch {}
                const isConfirming = confirmDeleteId === run.id
                const isExpanded = expandedRunId === run.id
                return (
                  <React.Fragment key={run.id}>
                  <tr style={isExpanded ? { background: 'var(--surface-2)' } : undefined}>
                    <td>
                      <span className="badge badge-accent badge-sm">
                        {run.pipeline_type.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${STATUS_BADGE[run.status] ?? 'badge-neutral'} badge-sm`}>
                        {run.status === 'running' && <span className="spinner spinner-xs" style={{ marginRight: 4 }} />}
                        {run.status}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, maxWidth: 280 }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                        {keywords.slice(0, 3).map((k) => (
                          <span key={k} className="badge badge-neutral badge-sm">{k}</span>
                        ))}
                        {keywords.length > 3 && (
                          <span className="badge badge-neutral badge-sm">+{keywords.length - 3}</span>
                        )}
                      </div>
                    </td>
                    <td style={{ fontSize: 13 }}>
                      {run.row_count != null ? run.row_count : '—'}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--t3)', whiteSpace: 'nowrap' }}>
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--t3)' }}>
                      {run.created_by?.split('@')[0] ?? '—'}
                    </td>
                    <td style={{ fontSize: 12, maxWidth: 240 }}>
                      {run.error_log ? (
                        <span style={{ color: 'var(--danger)', fontFamily: 'monospace', fontSize: 11 }}>
                          {run.error_log.slice(0, 120)}{run.error_log.length > 120 ? '…' : ''}
                        </span>
                      ) : '—'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {/* Results preview toggle */}
                        {run.status === 'completed' && (
                          <button
                            className="btn btn-ghost btn-xs"
                            title={isExpanded ? 'Hide results' : 'Preview results'}
                            onClick={() => setExpandedRunId(isExpanded ? null : run.id)}
                          >
                            {isExpanded ? '▲ Hide' : '▼ Results'}
                          </button>
                        )}

                        {/* View link */}
                        <button
                          className="btn btn-ghost btn-xs"
                          title="View run"
                          onClick={() => navigate(`/${encodeURIComponent(team)}/pipelines?run=${run.id}`)}
                        >
                          View
                        </button>

                        {/* Databricks run link */}
                        {run.databricks_run_id && (
                          <a
                            href={`https://dbc-34ec8d98-3f7f.cloud.databricks.com/jobs/runs/${run.databricks_run_id}`}
                            target="_blank"
                            rel="noreferrer"
                            className="btn btn-ghost btn-xs"
                            title="Open in Databricks"
                            style={{ textDecoration: 'none' }}
                          >
                            ↗
                          </a>
                        )}

                        {/* Delete */}
                        {isConfirming ? (
                          <>
                            <button
                              className="btn btn-danger btn-xs"
                              onClick={() => deleteMutation.mutate(run.id)}
                              disabled={deleteMutation.isPending}
                            >
                              {deleteMutation.isPending ? '…' : 'Yes'}
                            </button>
                            <button
                              className="btn btn-ghost btn-xs"
                              onClick={() => setConfirmDeleteId(null)}
                            >
                              No
                            </button>
                          </>
                        ) : (
                          <button
                            className="btn btn-ghost btn-xs"
                            title="Delete run"
                            style={{ color: 'var(--t-secondary)' }}
                            onClick={() => setConfirmDeleteId(run.id)}
                          >
                            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                              <path d="M3 4h10M6 4V2h4v2M5 4l1 9h4l1-9"/>
                            </svg>
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr style={{ background: 'var(--surface-2)' }}>
                      <td colSpan={8} style={{ padding: '16px 20px' }}>
                        <PipelineResults run={run} />
                      </td>
                    </tr>
                  )}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
