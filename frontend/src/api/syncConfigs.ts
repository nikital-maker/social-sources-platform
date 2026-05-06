import { api } from './client'

export interface SyncConfig {
  id: string
  spreadsheet_id: string
  spreadsheet_url: string
  spreadsheet_name: string
  tab_title: string
  gid: number
  team: string
  mapping_json: string
  platform_override: string
  manual_values_json: string
  meta_mapping_json: string
  sync_enabled: boolean
  sync_interval_minutes: number
  last_sync_at: string | null
  last_sync_rows: number | null
  last_sync_error: string | null
  created_at: string | null
  created_by: string | null
}

export interface SyncConfigCreate {
  spreadsheet_id: string
  spreadsheet_url: string
  spreadsheet_name: string
  tab_title: string
  gid: number
  team: string
  mapping_json?: string
  platform_override?: string
  manual_values_json?: string
  meta_mapping_json?: string
  sync_interval_minutes?: number
}

export interface SyncConfigUpdate {
  sync_enabled?: boolean
  sync_interval_minutes?: number
  mapping_json?: string
  platform_override?: string
  manual_values_json?: string
  meta_mapping_json?: string
}

export interface SyncResult {
  config_id: string
  imported: number
  skipped: number
  errors: string[]
}

export async function listSyncConfigs(team: string): Promise<SyncConfig[]> {
  const res = await api.get<SyncConfig[]>(`/sync-configs?team=${encodeURIComponent(team)}`)
  return res.data
}

export async function createSyncConfig(team: string, body: SyncConfigCreate): Promise<{ id: string }> {
  const res = await api.post<{ id: string }>(`/sync-configs?team=${encodeURIComponent(team)}`, body)
  return res.data
}

export async function updateSyncConfig(configId: string, body: SyncConfigUpdate): Promise<void> {
  await api.patch(`/sync-configs/${configId}`, body)
}

export async function deleteSyncConfig(configId: string): Promise<void> {
  await api.delete(`/sync-configs/${configId}`)
}

export async function triggerSync(configId: string): Promise<SyncResult> {
  const res = await api.post<SyncResult>(`/sync-configs/${configId}/sync`)
  return res.data
}
