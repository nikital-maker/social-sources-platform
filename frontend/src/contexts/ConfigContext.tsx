import { createContext, useContext } from 'react'
import type { AppConfig } from '../api/config'

const defaults: AppConfig = {
  teams: [],
  platforms: [],
  relevancy_options: [],
  workflow_teams: [],
}

export const ConfigContext = createContext<AppConfig>(defaults)

export function useConfig() {
  return useContext(ConfigContext)
}
