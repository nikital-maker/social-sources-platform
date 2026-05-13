import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTeamContext } from '../contexts/TeamContext'
import { getPipelineRun, startPipeline } from '../api/pipelines'
import type { GoogleDorkingConfig } from '../api/pipelines'
import { GoogleDorkingForm } from '../components/pipelines/GoogleDorkingForm'
import { PipelineResults } from '../components/pipelines/PipelineResults'
import { useToast } from '../components/ui/Toast'

export function Pipelines() {
  const { team } = useTeamContext()
  const queryClient = useQueryClient()
  const { addToast } = useToast()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [showForm, setShowForm] = useState(false)

  // selectedRunId comes from URL ?run=<id> so it survives navigation and page reload
  const selectedRunId = searchParams.get('run')

  function selectRun(id: string | null) {
    if (id) {
      setSearchParams({ run: id }, { replace: true })
    } else {
      setSearchParams({}, { replace: true })
    }
  }

  const { data: selectedRun } = useQuery({
    queryKey: ['pipeline-run', selectedRunId],
    queryFn: () => getPipelineRun(selectedRunId!),
    enabled: !!selectedRunId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'running' ? 5000 : false
    },
  })

  const mutation = useMutation({
    mutationFn: (config: GoogleDorkingConfig) => startPipeline(team, config),
    onSuccess: (run) => {
      addToast('Pipeline started — results will appear when the job completes.', 'success')
      setShowForm(false)
      selectRun(run.id)
      queryClient.invalidateQueries({ queryKey: ['pipeline-runs', team] })
    },
    onError: (err: Error) => {
      addToast(`Failed to start pipeline: ${err.message}`, 'error')
    },
  })

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Pipelines</h1>
          <p className="page-subtitle">Run scraping jobs and view results for <strong>{team}</strong></p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => navigate(`/${encodeURIComponent(team)}/pipelines/runs`)}
          >
            Run history
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => { setShowForm((v) => !v); selectRun(null) }}
          >
            {showForm ? 'Cancel' : '+ New Pipeline'}
          </button>
        </div>
      </div>

      {/* New pipeline form */}
      {showForm && (
        <div className="card card-md" style={{ marginBottom: 24 }}>
          <div className="card-header" style={{ marginBottom: 20 }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Google Dorking</h2>
            <span className="badge badge-accent badge-sm">Scale SERP API</span>
          </div>
          <GoogleDorkingForm
            onSubmit={(config) => mutation.mutate(config)}
            loading={mutation.isPending}
          />
        </div>
      )}

      {/* Selected run results */}
      {selectedRun && !showForm && (
        <div className="card card-md" style={{ marginBottom: 24 }}>
          <div className="card-header" style={{ marginBottom: 16 }}>
            <h2 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>
              Run results
            </h2>
            <button
              className="btn btn-ghost btn-xs"
              onClick={() => selectRun(null)}
            >✕ Close</button>
          </div>
          <PipelineResults run={selectedRun} />
        </div>
      )}

      {!showForm && !selectedRun && (
        <div style={{ padding: '48px 24px', color: 'var(--t3)', fontSize: 13, textAlign: 'center' }}>
          Click <strong>+ New Pipeline</strong> to start a scraping job, or{' '}
          <button
            className="btn btn-ghost btn-xs"
            style={{ display: 'inline' }}
            onClick={() => navigate(`/${encodeURIComponent(team)}/pipelines/runs`)}
          >
            view run history
          </button>.
        </div>
      )}
    </div>
  )
}
