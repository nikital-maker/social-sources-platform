import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { approveStaged, listStaging, rejectStaged } from '../api/staging'
import { ErrorBanner } from '../components/shared/ErrorBanner'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { LoadingState } from '../components/ui/Spinner'
import { useTeamContext } from '../contexts/TeamContext'

export function PendingReview() {
  const { team } = useTeamContext()
  const qc = useQueryClient()

  const { data = [], isLoading, error } = useQuery({
    queryKey: ['staging', team],
    queryFn: () => listStaging(team),
    staleTime: 30_000,
    enabled: !!team,
  })

  const approveMutation = useMutation({
    mutationFn: (url: string) => approveStaged(team, url),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staging', team] })
      qc.invalidateQueries({ queryKey: ['sources', team] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (url: string) => rejectStaged(url),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['staging', team] }),
  })

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="flex items-center gap-3">
          <h1 className="page-title">Pending Review</h1>
          {data.length > 0 && (
            <Badge variant="warning" size="md">{data.length}</Badge>
          )}
        </div>
        <p className="page-subtitle">
          Scraper-sourced entries awaiting approval into <strong style={{ color: 'var(--t-accent)' }}>{team}</strong>
        </p>
      </div>

      <ErrorBanner error={error} title="Load error" />
      <ErrorBanner error={approveMutation.error} title="Approve failed" />
      <ErrorBanner error={rejectMutation.error} title="Reject failed" />

      {isLoading ? (
        <LoadingState />
      ) : data.length === 0 ? (
        <div className="empty-state">
          <svg className="empty-icon" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="20" cy="20" r="14"/>
            <path d="M14 20l4 4 8-8"/>
          </svg>
          <p className="empty-text">All clear</p>
          <p className="empty-sub">No sources pending review</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {data.map((row) => (
            <ReviewCard
              key={row.id ?? row.url}
              row={row}
              onApprove={() => approveMutation.mutate(row.url!)}
              onReject={() => rejectMutation.mutate(row.url!)}
              isPending={approveMutation.isPending || rejectMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ReviewCard({
  row,
  onApprove,
  onReject,
  isPending,
}: {
  row: any
  onApprove: () => void
  onReject: () => void
  isPending: boolean
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="review-card">
      <div className="review-card-head" onClick={() => setExpanded((v) => !v)}>
        {row.platform && (
          <Badge variant="info" size="sm">{row.platform}</Badge>
        )}
        {row.scraper_name && (
          <Badge variant="neutral" size="sm">{row.scraper_name}</Badge>
        )}
        <span className="review-card-url flex-1 min-w-0">{row.url}</span>
        <svg
          width="13" height="13"
          viewBox="0 0 16 16" fill="none" stroke="var(--t3)" strokeWidth="2" strokeLinecap="round"
          style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s ease', flexShrink: 0 }}
        >
          <path d="M4 6l4 4 4-4"/>
        </svg>
      </div>

      {expanded && (
        <div className="review-card-body">
          <pre style={{ marginBottom: 14 }}>{JSON.stringify(row, null, 2)}</pre>
          <div className="flex gap-2">
            <Button variant="success" size="sm" loading={isPending} onClick={onApprove}>
              ✓ Approve
            </Button>
            <Button variant="danger" size="sm" loading={isPending} onClick={onReject}>
              ✗ Reject
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
