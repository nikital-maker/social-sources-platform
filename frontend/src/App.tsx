import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fetchConfig } from './api/config'
import type { AppConfig } from './api/config'
import { ConfigContext } from './contexts/ConfigContext'
import { TeamContext } from './contexts/TeamContext'
import { AppShell } from './components/layout/AppShell'
import { ToastProvider } from './components/ui/Toast'
import { Dashboard } from './pages/Dashboard'
import { Diagnostics } from './pages/Diagnostics'
import { ImportSources } from './pages/ImportSources'
import { PendingReview } from './pages/PendingReview'
import { RunScrapers } from './pages/RunScrapers'
import { ConnectedSheets } from './pages/ConnectedSheets'
import { SourcesBrowser } from './pages/SourcesBrowser'
import { TelegramWorkflow } from './pages/TelegramWorkflow'

const queryClient = new QueryClient()

function AppRoutes() {
  const [config, setConfig] = useState<AppConfig>({ teams: [], platforms: [], relevancy_options: [], workflow_teams: [] })
  const [configLoaded, setConfigLoaded] = useState(false)
  const [team, setTeam] = useState('')

  useEffect(() => {
    fetchConfig().then((cfg) => {
      setConfig(cfg)
      if (cfg.teams.length) {
        // Restore team from URL or default to first
        const urlTeam = decodeURIComponent(window.location.pathname.split('/')[1] ?? '')
        setTeam(cfg.teams.includes(urlTeam) ? urlTeam : cfg.teams[0])
      }
      setConfigLoaded(true)
    })
  }, [])

  if (!configLoaded) {
    return <div style={{ padding: 24, color: '#6b7280' }}>Loading…</div>
  }

  return (
    <ConfigContext.Provider value={config}>
      <TeamContext.Provider value={{ team, setTeam }}>
        <ToastProvider>
        <AppShell>
          <Routes>
            <Route path="/" element={
              config.teams.length
                ? <Navigate to={`/${encodeURIComponent(config.teams[0])}/sources`} replace />
                : <div>No teams configured.</div>
            } />
            <Route path="/:team/sources" element={<SourcesBrowser />} />
            <Route path="/:team/import" element={<ImportSources />} />
            <Route path="/:team/review" element={<PendingReview />} />
            <Route path="/:team/telegram" element={<TelegramWorkflow />} />
            <Route path="/:team/connected-sheets" element={<ConnectedSheets />} />
            <Route path="/:team/dashboard" element={<Dashboard />} />
            <Route path="/scrapers" element={<RunScrapers />} />
            <Route path="/diagnostics" element={<Diagnostics />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell>
        </ToastProvider>
      </TeamContext.Provider>
    </ConfigContext.Provider>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
