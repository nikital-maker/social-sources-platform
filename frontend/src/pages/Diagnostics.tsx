import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { Card, CardHeader } from '../components/ui/Card'
import { LoadingState } from '../components/ui/Spinner'

interface HealthResult { status: string }

export function Diagnostics() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const [health, config] = await Promise.all([
        api.get<HealthResult>('/health'),
        api.get('/config'),
      ])
      return { health: health.data, config: config.data }
    },
    staleTime: 0,
    retry: false,
  })

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Diagnostics</h1>
        <p className="page-subtitle">System health and configuration</p>
      </div>

      <div className="flex flex-col gap-4">
        {/* API Health */}
        <Card padding="lg">
          <CardHeader title="API Health" />
          {isLoading ? (
            <LoadingState text="Checking…" />
          ) : error ? (
            <div className="status-warn">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <circle cx="8" cy="8" r="6"/>
                <path d="M8 5v3M8 11v.5"/>
              </svg>
              API unreachable: {String(error)}
            </div>
          ) : (
            <div className="status-ok">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <circle cx="8" cy="8" r="6"/>
                <path d="M5.5 8l2 2 3-3"/>
              </svg>
              API is up — status: <strong>{data?.health.status}</strong>
            </div>
          )}
        </Card>

        {/* Config */}
        <Card padding="lg">
          <CardHeader title="App Config" />
          {data?.config ? (
            <pre>{JSON.stringify(data.config, null, 2)}</pre>
          ) : !isLoading ? (
            <p className="text-dim text-sm">Not available</p>
          ) : null}
        </Card>

        {/* Environment */}
        <Card padding="lg">
          <CardHeader title="Browser Environment" />
          <pre>{`Window origin: ${window.location.origin}\nAPI base: /api`}</pre>
        </Card>
      </div>
    </div>
  )
}
