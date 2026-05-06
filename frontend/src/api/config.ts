import { api } from './client'

export interface AppConfig {
  teams: string[]
  platforms: string[]
  relevancy_options: string[]
  workflow_teams: string[]
}

export async function fetchConfig(): Promise<AppConfig> {
  const res = await api.get<AppConfig>('/config')
  return res.data
}
