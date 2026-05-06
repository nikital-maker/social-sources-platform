import { api } from './client'

export interface ScraperJob {
  job_id: number
  name: string
  last_status: string
  last_run_at?: string
}

export async function listScrapers(): Promise<ScraperJob[]> {
  const res = await api.get<ScraperJob[]>('/scrapers')
  return res.data
}

export async function runScraper(jobId: number): Promise<{ run_id: number; run_url: string }> {
  const res = await api.post<{ run_id: number; run_url: string }>(`/scrapers/${jobId}/run`)
  return res.data
}
