import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listScrapers, runScraper } from '../api/scrapers'
import { ErrorBanner } from '../components/shared/ErrorBanner'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { LoadingState } from '../components/ui/Spinner'

export function RunScrapers() {
  const qc = useQueryClient()
  const [runUrls, setRunUrls] = useState<Record<number, string>>({})

  const { data = [], isLoading, error } = useQuery({
    queryKey: ['scrapers'],
    queryFn: listScrapers,
    staleTime: 30_000,
  })

  const triggerMutation = useMutation({
    mutationFn: (jobId: number) => runScraper(jobId),
    onSuccess: (result, jobId) => {
      setRunUrls((prev) => ({ ...prev, [jobId]: result.run_url }))
      qc.invalidateQueries({ queryKey: ['scrapers'] })
    },
  })

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Run Scrapers</h1>
        <p className="page-subtitle">Trigger Databricks scraper jobs</p>
      </div>

      <ErrorBanner error={error} title="Load error" />
      <ErrorBanner error={triggerMutation.error} title="Trigger failed" />

      {isLoading ? (
        <LoadingState />
      ) : data.length === 0 ? (
        <div className="empty-state">
          <svg className="empty-icon" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M8 20h24M20 8v24"/>
            <circle cx="20" cy="20" r="14"/>
          </svg>
          <p className="empty-text">No scrapers found</p>
          <p className="empty-sub">Jobs must be named with the <code>scraper_</code> prefix</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Job Name</th>
                <th>Last Status</th>
                <th>Last Run</th>
                <th style={{ width: 130 }}></th>
              </tr>
            </thead>
            <tbody>
              {data.map((job) => (
                <tr key={job.job_id}>
                  <td className="cell-primary cell-mono">{job.name}</td>
                  <td><ScraperStatusBadge status={job.last_status} /></td>
                  <td className="cell-mono text-xs text-dim">
                    {job.last_run_at ? job.last_run_at.slice(0, 16) : '—'}
                  </td>
                  <td>
                    {runUrls[job.job_id] ? (
                      <a
                        href={runUrls[job.job_id]}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent text-sm"
                      >
                        View run ↗
                      </a>
                    ) : (
                      <Button
                        variant="primary"
                        size="sm"
                        loading={triggerMutation.isPending}
                        onClick={() => triggerMutation.mutate(job.job_id)}
                      >
                        Run Now
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ScraperStatusBadge({ status }: { status: string }) {
  const map: Record<string, 'success' | 'danger' | 'info' | 'neutral'> = {
    SUCCESS: 'success',
    FAILED: 'danger',
    RUNNING: 'info',
    'Never run': 'neutral',
  }
  return (
    <Badge variant={map[status] ?? 'neutral'} size="sm">{status}</Badge>
  )
}
