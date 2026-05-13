import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PipelineResults } from '../components/pipelines/PipelineResults'
import type { PipelineRun } from '../api/pipelines'

vi.mock('../api/pipelines', () => ({
  getPipelineResults: vi.fn(),
}))

function makeRun(overrides: Partial<PipelineRun> = {}): PipelineRun {
  return {
    id: 'run-1',
    team: 'Child Safety',
    pipeline_type: 'google_dorking',
    config_json: JSON.stringify({ keywords: ['leaked', 'private'], timeframe: 30 }),
    status: 'completed',
    databricks_run_id: 12345,
    row_count: 42,
    created_at: '2026-05-12T10:00:00Z',
    created_by: 'nikital@activefence.com',
    completed_at: '2026-05-12T10:05:00Z',
    ...overrides,
  }
}

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

describe('PipelineResults', () => {
  it('shows status badge', () => {
    wrap(<PipelineResults run={makeRun({ status: 'completed' })} />)
    expect(screen.getByText('completed')).toBeInTheDocument()
  })

  it('shows row count badge', () => {
    wrap(<PipelineResults run={makeRun({ row_count: 42 })} />)
    expect(screen.getByText('42 results')).toBeInTheDocument()
  })

  it('shows keyword and timeframe badges from config', () => {
    wrap(<PipelineResults run={makeRun()} />)
    expect(screen.getByText('leaked')).toBeInTheDocument()
    expect(screen.getByText('private')).toBeInTheDocument()
    expect(screen.getByText('30d')).toBeInTheDocument()
  })

  it('shows spinner and message when status is running', () => {
    wrap(<PipelineResults run={makeRun({ status: 'running' })} />)
    expect(screen.getByText(/job is running on databricks/i)).toBeInTheDocument()
  })

  it('shows spinner and message when status is pending', () => {
    wrap(<PipelineResults run={makeRun({ status: 'pending' })} />)
    expect(screen.getByText(/job is running on databricks/i)).toBeInTheDocument()
  })

  it('shows failed message with link when status is failed', () => {
    wrap(<PipelineResults run={makeRun({ status: 'failed', databricks_run_id: 99 })} />)
    expect(screen.getByText(/job failed/i)).toBeInTheDocument()
    expect(screen.getByText(/view run/i)).toBeInTheDocument()
  })
})
