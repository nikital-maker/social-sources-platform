import { api } from './client'

export interface SheetTab {
  id: number
  title: string
}

export interface SheetData {
  columns: string[]
  rows: string[][]
}

export async function listSheets(url: string): Promise<SheetTab[]> {
  const res = await api.get<SheetTab[]>('/gsheets/sheets', { params: { url } })
  return res.data
}

export async function getSheetData(id: string, gid: number): Promise<SheetData> {
  const res = await api.get<SheetData>('/gsheets/data', { params: { id, gid } })
  return res.data
}

export async function updateSheet(body: { sheet_id: string; tab_title: string; rows: string[][] }): Promise<void> {
  await api.put('/gsheets/data', body)
}

export async function renameTab(body: { sheet_id: string; old_title: string; new_title: string }): Promise<void> {
  await api.patch('/gsheets/tab', body)
}
