import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { getPipelineResults } from '../../api/pipelines'
import type { PipelineRun } from '../../api/pipelines'
import { Spinner } from '../ui/Spinner'
import { useState } from 'react'

interface Props {
  run: PipelineRun
}

const STATUS_BADGE: Record<string, string> = {
  pending: 'badge-neutral',
  running: 'badge-warning',
  completed: 'badge-success',
  failed: 'badge-danger',
}

export function PipelineResults({ run }: Props) {
  const [page, setPage] = useState(1)
  const pageSize = 50

  const { data, isLoading } = useQuery({
    queryKey: ['pipeline-results', run.id, page],
    queryFn: () => getPipelineResults(run.id, page, pageSize),
    enabled: run.status === 'completed',
  })

  const totalPages = data ? Math.ceil(data.total / pageSize) : 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Run header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span className={`badge ${STATUS_BADGE[run.status] ?? 'badge-neutral'} badge-sm`}>
          {run.status}
        </span>
        {run.row_count != null && (
          <span className="badge badge-neutral badge-sm">{run.row_count} results</span>
        )}
        <span style={{ fontSize: 12, color: 'var(--t3)' }}>
          {new Date(run.created_at).toLocaleString()}
        </span>
        {run.created_by && (
          <span style={{ fontSize: 12, color: 'var(--t3)' }}>by {run.created_by}</span>
        )}
      </div>

      {/* Config summary */}
      <ConfigSummary configJson={run.config_json} />

      {/* Results */}
      {run.status === 'running' || run.status === 'pending' ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--t2)', fontSize: 13, padding: '16px 0' }}>
          <Spinner size="sm" />
          Job is running on Databricks… results will appear here when complete.
        </div>
      ) : run.status === 'failed' ? (
        <div className="badge badge-danger badge-sm" style={{ alignSelf: 'flex-start' }}>
          Job failed — check Databricks for details
          {run.databricks_run_id && (
            <a
              href={`https://dbc-34ec8d98-3f7f.cloud.databricks.com/jobs/runs/${run.databricks_run_id}`}
              target="_blank"
              rel="noreferrer"
              style={{ marginLeft: 6, color: 'inherit' }}
            >
              View run ↗
            </a>
          )}
        </div>
      ) : isLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner /></div>
      ) : !data || data.items.length === 0 ? (
        <div style={{ color: 'var(--t3)', fontSize: 13 }}>No results found.</div>
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>URL</th>
                  <th>Title</th>
                  <th>Snippet</th>
                  <th>Query</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td style={{ maxWidth: 260, wordBreak: 'break-all' }}>
                      {row.href ? (
                        <a href={row.href} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', fontSize: 12 }}>
                          {row.href.length > 60 ? row.href.slice(0, 60) + '…' : row.href}
                        </a>
                      ) : '—'}
                    </td>
                    <td style={{ maxWidth: 220, fontSize: 13 }}>{row.title || '—'}</td>
                    <td style={{ maxWidth: 320, fontSize: 12, color: 'var(--t2)' }}>{row.body || '—'}</td>
                    <td style={{ fontSize: 11, color: 'var(--t3)', maxWidth: 160 }}>{row.query || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >← Prev</button>
              <span style={{ fontSize: 12, color: 'var(--t2)' }}>
                {page} / {totalPages} · {data.total} results
              </span>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >Next →</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function ConfigSummary({ configJson }: { configJson: string }): React.ReactElement | null {
  let config: Record<string, unknown> = {}
  try { config = JSON.parse(configJson) } catch { return null }

  const keywords = (config.keywords as string[] | undefined) ?? []
  const sites = (config.sites as string[] | undefined) ?? []

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, fontSize: 12, color: 'var(--t2)' }}>
      <span style={{ color: 'var(--t3)' }}>Keywords:</span>
      {keywords.map((k) => <span key={k} className="badge badge-accent badge-sm">{k}</span>)}
      {sites.length > 0 && (
        <>
          <span style={{ color: 'var(--t3)', marginLeft: 6 }}>Sites:</span>
          {sites.map((s) => <span key={s} className="badge badge-neutral badge-sm">{s}</span>)}
        </>
      )}
      {config.timeframe != null && (
        <span className="badge badge-neutral badge-sm">{String(config.timeframe)}d</span>
      )}
    </div>
  )
}
