import { api } from './client'
import type { Source } from './sources'

export async function listStaging(team: string): Promise<Source[]> {
  const res = await api.get<Source[]>('/staging', { params: { team } })
  return res.data
}

export async function approveStaged(team: string, url: string): Promise<void> {
  await api.post('/staging/approve', { url }, { params: { team } })
}

export async function rejectStaged(url: string): Promise<void> {
  await api.post('/staging/reject', { url })
}
