import { api } from './client'

export interface TaskStatus {
  key: string
  life_cycle: string
  result?: string
  display_state: string
  font_color: string
  fill_color: string
  depends_on: string[]
}

export interface RunStatus {
  run_id: number
  life_cycle: string
  result?: string
  message: string
  is_running: boolean
  is_done: boolean
  elapsed_seconds?: number
  tasks: TaskStatus[]
}

export interface WorkflowConfig {
  team: string
  job_id: string
  sheet_id: string
  job_url: string
  sheet_url: string
}

export interface JobDetail {
  job_id: number
  name: string
  last_run_at?: string
  active_run_id?: number
  parameters: { name: string; default: string }[]
  tasks: {
    key: string
    type: string
    path: string
    params: string
    depends_on: string[]
    cluster: string
  }[]
}

export async function getWorkflowConfig(team: string): Promise<WorkflowConfig | null> {
  const res = await api.get<WorkflowConfig | null>('/jobs/workflow-config', { params: { team } })
  return res.data
}

export async function getJobDetails(jobId: number): Promise<JobDetail> {
  const res = await api.get<JobDetail>(`/jobs/${jobId}/details`)
  return res.data
}

export async function triggerJob(jobId: number): Promise<{ run_id: number; run_url: string }> {
  const res = await api.post<{ run_id: number; run_url: string }>(`/jobs/${jobId}/run`)
  return res.data
}

export async function cancelRun(runId: number): Promise<void> {
  await api.post(`/jobs/runs/${runId}/cancel`)
}

export async function getRunStatus(runId: number): Promise<RunStatus> {
  const res = await api.get<RunStatus>(`/jobs/runs/${runId}/status`)
  return res.data
}
