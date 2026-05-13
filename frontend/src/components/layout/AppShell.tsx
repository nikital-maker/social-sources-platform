import { NavLink, useNavigate } from 'react-router-dom'
import { useConfig } from '../../contexts/ConfigContext'
import { useTeamContext } from '../../contexts/TeamContext'

const NAV_TEAM = [
  { label: 'Sources Browser',     path: 'sources',          icon: <IconSources /> },
  { label: 'Import Sources',      path: 'import',           icon: <IconImport /> },
  { label: 'Connected Sheets',    path: 'connected-sheets', icon: <IconSheets /> },
  { label: 'Pending Review',      path: 'review',           icon: <IconReview /> },
  { label: 'Telegram Workflow',   path: 'telegram',         icon: <IconTelegram /> },
  { label: 'Dashboard',           path: 'dashboard',        icon: <IconDashboard /> },
  { label: 'Pipelines',           path: 'pipelines',        icon: <IconPipelines /> },
]

const NAV_GLOBAL = [
  { label: 'Diagnostics',   path: '/diagnostics', icon: <IconDiagnostics /> },
]

interface Props { children: React.ReactNode }

export function AppShell({ children }: Props) {
  const { teams } = useConfig()
  const { team, setTeam } = useTeamContext()
  const navigate = useNavigate()

  function handleTeamChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = e.target.value
    setTeam(next)
    navigate(`/${encodeURIComponent(next)}/sources`)
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">
            <LogoMark />
          </div>
          <div className="sidebar-logo-text">
            <span className="sidebar-logo-name">Sources</span>
            <span className="sidebar-logo-sub">Intelligence Platform</span>
          </div>
        </div>

        {/* Team selector */}
        <div className="sidebar-team">
          <div className="sidebar-team-label">Team</div>
          <select
            value={team}
            onChange={handleTeamChange}
            className="sidebar-team-select"
          >
            {teams.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          <div className="sidebar-nav-section">
            <div className="sidebar-nav-section-label">Workspace</div>
            {NAV_TEAM.map(({ label, path, icon }) => {
              const to = `/${encodeURIComponent(team)}/${path}`
              return (
                <NavLink
                  key={path}
                  to={to}
                  className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                >
                  <span className="nav-item-icon">{icon}</span>
                  {label}
                </NavLink>
              )
            })}
          </div>

          <div className="sidebar-nav-section" style={{ marginTop: 8 }}>
            <div className="sidebar-nav-section-label">Platform</div>
            {NAV_GLOBAL.map(({ label, path, icon }) => (
              <NavLink
                key={path}
                to={path}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <span className="nav-item-icon">{icon}</span>
                {label}
              </NavLink>
            ))}
          </div>
        </nav>

        <div className="sidebar-footer">v2 · social-sources</div>
      </aside>

      <main className="main-content">
        {children}
      </main>
    </div>
  )
}

/* ── Icons ─────────────────────────────────────────────────── */

function LogoMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M8 1L15 5V11L8 15L1 11V5L8 1Z" fill="rgba(124,92,252,0.25)" stroke="#7c5cfc" strokeWidth="1.3"/>
      <path d="M8 5L11.5 7V11L8 13L4.5 11V7L8 5Z" fill="#7c5cfc"/>
    </svg>
  )
}

function IconSources() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="5" height="5" rx="1"/>
      <rect x="9" y="2" width="5" height="5" rx="1"/>
      <rect x="2" y="9" width="5" height="5" rx="1"/>
      <rect x="9" y="9" width="5" height="5" rx="1"/>
    </svg>
  )
}

function IconImport() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 2v9"/>
      <path d="M5 8l3 3 3-3"/>
      <path d="M2 13h12"/>
    </svg>
  )
}

function IconReview() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="8" r="6"/>
      <path d="M8 5v3.5l2.5 1.5"/>
    </svg>
  )
}

function IconTelegram() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2L1 6.5l5 1.5 2 5 2-3 4 3L14 2z"/>
      <path d="M6 8l4-3"/>
    </svg>
  )
}

function IconSheets() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="12" height="12" rx="2"/>
      <path d="M2 6h12M2 10h12M6 2v12M10 2v12"/>
    </svg>
  )
}

function IconDashboard() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="9" width="3" height="5" rx="0.5"/>
      <rect x="6.5" y="5.5" width="3" height="8.5" rx="0.5"/>
      <rect x="11" y="2" width="3" height="12" rx="0.5"/>
    </svg>
  )
}

function IconPipelines() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4h3v8H2z"/>
      <path d="M6.5 2h3v12h-3z"/>
      <path d="M11 6h3v6h-3z"/>
    </svg>
  )
}

function IconDiagnostics() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 8h2l2-5 3 10 2-6 1.5 1H15"/>
    </svg>
  )
}
