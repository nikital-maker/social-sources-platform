import { useEffect, useState } from 'react'
import type { RunStatus } from '../api/jobs'

export function useJobMonitor(runId: number | null) {
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) {
      setStatus(null)
      setError(null)
      return
    }

    const es = new EventSource(`/api/jobs/runs/${runId}/stream`)

    es.addEventListener('status', (e) => {
      setStatus(JSON.parse(e.data))
      setError(null)
    })

    es.addEventListener('done', (e) => {
      setStatus(JSON.parse(e.data))
      setError(null)
      es.close()
    })

    es.addEventListener('error', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        setError(data.detail ?? 'Unknown error')
      } catch {
        setError('Stream error')
      }
      es.close()
    })

    es.onerror = () => {
      setError('Connection lost')
      es.close()
    }

    return () => es.close()
  }, [runId])

  return { status, error }
}
