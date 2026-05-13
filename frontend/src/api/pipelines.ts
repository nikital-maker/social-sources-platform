import { api } from './client'

export interface GoogleDorkingConfig {
  keywords: string[]
  sites: string[]
  clients: string[]
  rule_out: string[]
  timeframe: 7 | 30 | 90 | 365
  num_of_results: number
  verbatim: boolean
}

export interface PipelineRun {
  id: string
  team: string
  pipeline_type: string
  config_json: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  databricks_run_id: number | null
  row_count: number | null
  error_log: string | null
  created_at: string
  created_by: string | null
  completed_at: string | null
}

export interface PipelineRunsPage {
  items: PipelineRun[]
  total: number
}

export interface GoogleDorkingResult {
  id: string
  pipeline_run_id: string
  team: string
  query: string | null
  href: string | null
  title: string | null
  body: string | null
  created_at: string
}

export interface PipelineResultsPage {
  items: GoogleDorkingResult[]
  total: number
  page: number
  page_size: number
}

export async function listPipelineRuns(team: string, page = 1, pageSize = 20): Promise<PipelineRunsPage> {
  const res = await api.get('/pipelines', { params: { team, page, page_size: pageSize } })
  return res.data
}

export async function startPipeline(team: string, config: GoogleDorkingConfig): Promise<PipelineRun> {
  const res = await api.post('/pipelines', {
    team,
    pipeline_type: 'google_dorking',
    config,
  })
  return res.data
}

export async function getPipelineRun(runId: string): Promise<PipelineRun> {
  const res = await api.get(`/pipelines/${runId}`)
  return res.data
}

export async function getRecentPipelineErrors(limit = 20): Promise<PipelineRun[]> {
  const res = await api.get('/pipelines/errors', { params: { limit } })
  return res.data
}

export async function deletePipelineRun(runId: string): Promise<void> {
  await api.delete(`/pipelines/${runId}`)
}

export async function getPipelineResults(runId: string, page = 1, pageSize = 50): Promise<PipelineResultsPage> {
  const res = await api.get(`/pipelines/${runId}/results`, { params: { page, page_size: pageSize } })
  return res.data
}
