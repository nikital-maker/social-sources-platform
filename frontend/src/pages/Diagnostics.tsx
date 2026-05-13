import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { getRecentPipelineErrors } from '../api/pipelines'
import { Card, CardHeader } from '../components/ui/Card'
import { LoadingState } from '../components/ui/Spinner'

interface HealthResult { status: string }

interface LogEntry {
  ts: string
  level: string
  logger: string
  message: string
}

const LEVEL_COLORS: Record<string, string> = {
  ERROR: 'var(--danger)',
  CRITICAL: 'var(--danger)',
  WARNING: '#f59e0b',
  INFO: 'var(--t2)',
  DEBUG: 'var(--t3)',
}

export function Diagnostics() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const [health, config] = await Promise.all([
        api.get<HealthResult>('/health'),
        api.get('/config'),
      ])
      return { health: health.data, config: config.data }
    },
    staleTime: 0,
    retry: false,
  })

  const { data: logs, isLoading: logsLoading } = useQuery({
    queryKey: ['app-logs'],
    queryFn: async () => {
      const res = await api.get<LogEntry[]>('/logs?n=200')
      return res.data
    },
    staleTime: 0,
    refetchInterval: 10_000,
    retry: false,
  })

  const { data: pipelineErrors, isLoading: errorsLoading } = useQuery({
    queryKey: ['pipeline-errors'],
    queryFn: () => getRecentPipelineErrors(20),
    staleTime: 30_000,
    retry: false,
  })

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Diagnostics</h1>
        <p className="page-subtitle">System health and configuration</p>
      </div>

      <div className="flex flex-col gap-4">
        {/* API Health */}
        <Card padding="lg">
          <CardHeader title="API Health" />
          {isLoading ? (
            <LoadingState text="Checking…" />
          ) : error ? (
            <div className="status-warn">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <circle cx="8" cy="8" r="6"/>
                <path d="M8 5v3M8 11v.5"/>
              </svg>
              API unreachable: {String(error)}
            </div>
          ) : (
            <div className="status-ok">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <circle cx="8" cy="8" r="6"/>
                <path d="M5.5 8l2 2 3-3"/>
              </svg>
              API is up — status: <strong>{data?.health.status}</strong>
            </div>
          )}
        </Card>

        {/* Pipeline Errors */}
        <Card padding="lg">
          <CardHeader title="Pipeline Errors (recent 20)" />
          {errorsLoading ? (
            <LoadingState text="Loading…" />
          ) : !pipelineErrors || pipelineErrors.length === 0 ? (
            <p className="text-dim text-sm">No failed pipeline runs.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {pipelineErrors.map((run) => {
                let keywords: string[] = []
                try { keywords = JSON.parse(run.config_json).keywords ?? [] } catch {}
                return (
                  <div
                    key={run.id}
                    style={{
                      padding: '12px 14px',
                      border: '1px solid var(--border-1)',
                      borderLeft: '3px solid var(--danger)',
                      borderRadius: 6,
                      background: 'var(--surface-2)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, flexWrap: 'wrap', gap: 4 }}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        <span className="badge badge-danger badge-sm">failed</span>
                        <span className="badge badge-accent badge-sm">{run.pipeline_type.replace(/_/g, ' ')}</span>
                        <span style={{ fontSize: 12, color: 'var(--t3)' }}>team: {run.team}</span>
                        {keywords.length > 0 && (
                          <span style={{ fontSize: 12, color: 'var(--t2)' }}>
                            keywords: {keywords.slice(0, 3).join(', ')}{keywords.length > 3 ? ` +${keywords.length - 3}` : ''}
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: 12, color: 'var(--t3)', whiteSpace: 'nowrap' }}>
                        {new Date(run.created_at).toLocaleString()} · {run.created_by?.split('@')[0] ?? '—'}
                      </span>
                    </div>
                    {run.error_log ? (
                      <pre style={{
                        margin: 0,
                        fontSize: 11,
                        color: 'var(--danger)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        maxHeight: 200,
                        overflowY: 'auto',
                        background: 'var(--surface-1)',
                        padding: '8px 10px',
                        borderRadius: 4,
                      }}>
                        {run.error_log}
                      </pre>
                    ) : (
                      <span style={{ fontSize: 12, color: 'var(--t3)', fontStyle: 'italic' }}>No error log captured.</span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        {/* App Logs */}
        <Card padding="lg">
          <CardHeader title="Recent App Logs (last 200)" />
          {logsLoading ? (
            <LoadingState text="Loading…" />
          ) : !logs || logs.length === 0 ? (
            <p className="text-dim text-sm">No logs captured yet.</p>
          ) : (
            <div style={{
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: 11,
              lineHeight: 1.6,
              maxHeight: 480,
              overflowY: 'auto',
              background: 'var(--surface-1)',
              border: '1px solid var(--border-1)',
              borderRadius: 6,
              padding: '8px 0',
            }}>
              {[...logs].reverse().map((entry, i) => (
                <div
                  key={i}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '160px 56px 1fr',
                    gap: '0 10px',
                    padding: '1px 12px',
                    borderBottom: i < logs.length - 1 ? '1px solid var(--border-0)' : undefined,
                  }}
                >
                  <span style={{ color: 'var(--t3)', whiteSpace: 'nowrap' }}>
                    {new Date(entry.ts).toLocaleString()}
                  </span>
                  <span style={{ color: LEVEL_COLORS[entry.level] ?? 'var(--t2)', fontWeight: 600 }}>
                    {entry.level}
                  </span>
                  <span style={{ color: 'var(--t1)', wordBreak: 'break-word' }}>
                    {entry.message}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Config */}
        <Card padding="lg">
          <CardHeader title="App Config" />
          {data?.config ? (
            <pre>{JSON.stringify(data.config, null, 2)}</pre>
          ) : !isLoading ? (
            <p className="text-dim text-sm">Not available</p>
          ) : null}
        </Card>

        {/* Environment */}
        <Card padding="lg">
          <CardHeader title="Browser Environment" />
          <pre>{`Window origin: ${window.location.origin}\nAPI base: /api`}</pre>
        </Card>
      </div>
    </div>
  )
}
