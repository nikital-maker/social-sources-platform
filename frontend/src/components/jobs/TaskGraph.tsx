import type { TaskStatus } from '../../api/jobs'

interface Props {
  tasks: TaskStatus[]
}

const STATE_CONFIG: Record<string, { icon: string; cls: string }> = {
  SUCCESS:            { icon: '✓', cls: 'badge-success' },
  RUNNING:            { icon: '▶', cls: 'badge-info' },
  TERMINATING:        { icon: '▶', cls: 'badge-info' },
  FAILED:             { icon: '✗', cls: 'badge-danger' },
  INTERNAL_ERROR:     { icon: '✗', cls: 'badge-danger' },
  TIMEDOUT:           { icon: '✗', cls: 'badge-danger' },
  PENDING:            { icon: '○', cls: 'badge-neutral' },
  QUEUED:             { icon: '○', cls: 'badge-neutral' },
  BLOCKED:            { icon: '○', cls: 'badge-neutral' },
  WAITING_FOR_RETRY:  { icon: '↻', cls: 'badge-warning' },
  SKIPPED:            { icon: '—', cls: 'badge-neutral' },
}

export function TaskGraph({ tasks }: Props) {
  if (!tasks.length) return null

  return (
    <div className="flex flex-wrap gap-2" style={{ margin: '12px 0' }}>
      {tasks.map((t) => {
        const cfg = STATE_CONFIG[t.display_state] ?? { icon: '?', cls: 'badge-neutral' }
        return (
          <div
            key={t.key}
            className={`task-badge ${cfg.cls}`}
            title={t.depends_on.length ? `Depends on: ${t.depends_on.join(', ')}` : undefined}
          >
            <span>{cfg.icon}</span>
            <span>{t.key}</span>
            <span style={{ opacity: 0.65, fontSize: 10 }}>{t.display_state}</span>
          </div>
        )
      })}
    </div>
  )
}
