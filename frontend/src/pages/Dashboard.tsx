import { useQuery } from '@tanstack/react-query'
import { getDashboard } from '../api/sources'
import { ErrorBanner } from '../components/shared/ErrorBanner'
import { Card, CardHeader } from '../components/ui/Card'
import { LoadingState } from '../components/ui/Spinner'
import { useTeamContext } from '../contexts/TeamContext'

export function Dashboard() {
  const { team } = useTeamContext()
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', team],
    queryFn: () => getDashboard(team),
    staleTime: 60_000,
    enabled: !!team,
  })

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Overview for team <strong style={{ color: 'var(--t-accent)' }}>{team}</strong></p>
      </div>

      <ErrorBanner error={error} title="Dashboard error" />

      {isLoading ? (
        <LoadingState />
      ) : data ? (
        <>
          {/* KPIs */}
          <div className="kpi-grid">
            <KpiCard value={data.total_sources} label="Total Sources" />
            <KpiCard value={data.added_this_week} label="Added This Week" accent />
            <KpiCard value={data.platforms_count} label="Platforms" />
          </div>

          {/* Bar charts */}
          <div className="charts-grid">
            <BarChartCard title="By Platform" data={data.by_platform} />
            <BarChartCard title="By Relevancy" data={data.by_relevancy} />
          </div>

          {/* Line chart */}
          <Card padding="lg">
            <CardHeader title="Sources added per day — last 30 days" />
            {data.daily_counts.length === 0 ? (
              <p className="text-muted text-sm">No data yet.</p>
            ) : (
              <LineChart points={data.daily_counts} />
            )}
          </Card>
        </>
      ) : null}
    </div>
  )
}

function KpiCard({ value, label, accent }: { value: number; label: string; accent?: boolean }) {
  return (
    <div className="kpi-card">
      <div className="kpi-value" style={accent ? { color: 'var(--t-accent)' } : undefined}>
        {value.toLocaleString()}
      </div>
      <div className="kpi-label">{label}</div>
    </div>
  )
}

function BarChartCard({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1])
  const max = Math.max(...entries.map(([, v]) => v), 1)

  return (
    <Card padding="lg">
      <CardHeader title={title} />
      {entries.length === 0 ? (
        <p className="text-dim text-sm">No data.</p>
      ) : (
        <div>
          {entries.map(([key, val]) => (
            <div key={key} className="chart-bar-row">
              <div className="chart-bar-label" title={key}>{key || '—'}</div>
              <div className="chart-bar-track">
                <div className="chart-bar-fill" style={{ width: `${(val / max) * 100}%` }} />
              </div>
              <div className="chart-bar-value">{val}</div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function LineChart({ points }: { points: { date: string; count: number }[] }) {
  const max = Math.max(...points.map((p) => p.count), 1)
  const w = 600
  const h = 90
  const padX = 8
  const padY = 12

  const xs = points.map((_, i) => padX + (i / (points.length - 1)) * (w - 2 * padX))
  const ys = points.map((p) => h - padY - (p.count / max) * (h - 2 * padY))

  const linePath = xs.map((x, i) => `${i === 0 ? 'M' : 'L'} ${x} ${ys[i]}`).join(' ')
  const areaPath = `${linePath} L ${xs[xs.length - 1]} ${h} L ${xs[0]} ${h} Z`

  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 90, display: 'block' }}>
      <defs>
        <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.25" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#lineGrad)" />
      <path d={linePath} fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      {points.map((p, i) => (
        <circle key={p.date} cx={xs[i]} cy={ys[i]} r={2.5} fill="var(--accent)">
          <title>{p.date}: {p.count}</title>
        </circle>
      ))}
    </svg>
  )
}
