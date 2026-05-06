import { createContext, useContext } from 'react'

export interface TeamContextValue {
  team: string
  setTeam: (t: string) => void
}

export const TeamContext = createContext<TeamContextValue>({
  team: '',
  setTeam: () => {},
})

export function useTeamContext() {
  return useContext(TeamContext)
}
