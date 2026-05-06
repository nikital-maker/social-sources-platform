import { api } from './client'

export interface Source {
  id: string
  url: string
  platform?: string
  team?: string
  abuse_area?: string
  sub_abuse_area?: string
  notes?: string
  relevancy?: string
  metadata?: string
  added_at?: string
  added_by?: string
}

export interface SourcesPage {
  items: Source[]
  total: number
}

export interface SourceFilters {
  platform?: string
  keyword?: string
  abuse_area?: string
  sub_abuse_area?: string
  relevancy?: string
  added_by?: string
}

export interface SourceCreate {
  url: string
  platform?: string
  abuse_area?: string
  sub_abuse_area?: string
  notes?: string
  relevancy?: string
  auto_detect_platform?: boolean
}

export interface FilterOptions {
  platforms: string[]
  abuse_areas: string[]
  sub_abuse_areas: string[]
  relevancies: string[]
  added_by: string[]
}

export interface DashboardData {
  total_sources: number
  added_this_week: number
  platforms_count: number
  by_platform: Record<string, number>
  by_relevancy: Record<string, number>
  daily_counts: { date: string; count: number }[]
}

export async function listSources(
  team: string,
  filters?: SourceFilters,
  limit = 100,
  offset = 0,
): Promise<SourcesPage> {
  const res = await api.get<SourcesPage>('/sources', {
    params: { team, ...filters, limit, offset },
  })
  return res.data
}

export async function getFilterOptions(team: string): Promise<FilterOptions> {
  const res = await api.get<FilterOptions>('/sources/filter-options', { params: { team } })
  return res.data
}

export async function addSource(team: string, body: SourceCreate): Promise<Source> {
  const res = await api.post<Source>('/sources', body, { params: { team } })
  return res.data
}

export async function deleteSources(team: string, ids: string[]): Promise<{ deleted: number }> {
  const res = await api.delete<{ deleted: number }>('/sources', { data: { ids }, params: { team } })
  return res.data
}

export async function wipeAllSources(team: string): Promise<{ deleted: number }> {
  const res = await api.delete<{ deleted: number }>('/sources/wipe-all', { params: { team } })
  return res.data
}

export function exportSourcesUrl(team: string, filters?: SourceFilters): string {
  const q = new URLSearchParams({ team, ...(filters as Record<string, string>) })
  // strip empty values
  for (const [k, v] of Array.from(q.entries())) {
    if (!v) q.delete(k)
  }
  return `/api/sources/export?${q}`
}

export async function getDashboard(team: string): Promise<DashboardData> {
  const res = await api.get<DashboardData>('/sources/dashboard', { params: { team } })
  return res.data
}
