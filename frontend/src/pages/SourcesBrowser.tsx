import { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { SourceFilters } from '../api/sources'
import { deleteSources, exportSourcesUrl, getFilterOptions, listSources, wipeAllSources } from '../api/sources'
import { ErrorBanner } from '../components/shared/ErrorBanner'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Input, Select } from '../components/ui/Input'
import { LoadingState } from '../components/ui/Spinner'
import { useTeamContext } from '../contexts/TeamContext'

const PAGE_SIZE = 100

export function SourcesBrowser() {
  const { team } = useTeamContext()
  const qc = useQueryClient()

  const [filters, setFilters] = useState<SourceFilters>({})
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [confirmWipe, setConfirmWipe] = useState(false)

  function setFilter(key: keyof SourceFilters, val: string) {
    setFilters((f) => ({ ...f, [key]: val || undefined }))
    setPage(0)
    setSelected(new Set())
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ['sources', team, filters, page],
    queryFn: () => listSources(team, filters, PAGE_SIZE, page * PAGE_SIZE),
    staleTime: 60_000,
    enabled: !!team,
  })

  const { data: filterOptions } = useQuery({
    queryKey: ['filter-options', team],
    queryFn: () => getFilterOptions(team),
    staleTime: 5 * 60_000,
    enabled: !!team,
  })

  const deleteMutation = useMutation({
    mutationFn: (ids: string[]) => deleteSources(team, ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources', team] })
      setSelected(new Set())
      setConfirmDelete(false)
    },
  })

  const wipeMutation = useMutation({
    mutationFn: () => wipeAllSources(team),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sources', team] })
      qc.invalidateQueries({ queryKey: ['filter-options', team] })
      setSelected(new Set())
      setConfirmWipe(false)
    },
  })

  const rows = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  function toggleRow(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleAll() {
    setSelected((prev) =>
      prev.size === rows.length ? new Set() : new Set(rows.map((s) => s.id))
    )
  }

  const exportUrl = exportSourcesUrl(team, filters)

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Sources Browser</h1>
        <p className="page-subtitle">Team: <strong style={{ color: 'var(--t-accent)' }}>{team}</strong></p>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        <div style={{ minWidth: 150 }}>
          <Select label="Platform" value={filters.platform ?? ''} onChange={(e) => setFilter('platform', e.target.value)}>
            <option value="">All platforms</option>
            {filterOptions?.platforms.map((p) => <option key={p} value={p}>{p}</option>)}
          </Select>
        </div>
        <div style={{ minWidth: 160 }}>
          <Select label="Abuse Area" value={filters.abuse_area ?? ''} onChange={(e) => setFilter('abuse_area', e.target.value)}>
            <option value="">All areas</option>
            {filterOptions?.abuse_areas.map((a) => <option key={a} value={a}>{a}</option>)}
          </Select>
        </div>
        <div style={{ minWidth: 160 }}>
          <Select label="Sub Abuse Area" value={filters.sub_abuse_area ?? ''} onChange={(e) => setFilter('sub_abuse_area', e.target.value)}>
            <option value="">All sub-areas</option>
            {filterOptions?.sub_abuse_areas.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
        </div>
        <div style={{ minWidth: 140 }}>
          <Select label="Relevancy" value={filters.relevancy ?? ''} onChange={(e) => setFilter('relevancy', e.target.value)}>
            <option value="">All relevancy</option>
            {filterOptions?.relevancies.map((r) => <option key={r} value={r}>{r}</option>)}
          </Select>
        </div>
        <div style={{ minWidth: 150 }}>
          <Select label="Added By" value={filters.added_by ?? ''} onChange={(e) => setFilter('added_by', e.target.value)}>
            <option value="">Anyone</option>
            {filterOptions?.added_by.map((u) => <option key={u} value={u}>{u}</option>)}
          </Select>
        </div>
        <div style={{ minWidth: 200, flex: 1 }}>
          <Input
            label="Search URL / Notes"
            value={filters.keyword ?? ''}
            onChange={(e) => setFilter('keyword', e.target.value)}
            placeholder="keyword…"
          />
        </div>
        <div style={{ alignSelf: 'flex-end', display: 'flex', gap: 8 }}>
          {Object.values(filters).some(Boolean) && (
            <Button variant="ghost" size="sm" onClick={() => { setFilters({}); setPage(0) }}>
              Clear
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => { qc.invalidateQueries({ queryKey: ['sources', team] }); qc.invalidateQueries({ queryKey: ['filter-options', team] }) }}>
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M1 8a7 7 0 0 1 13-3.5M15 8a7 7 0 0 1-13 3.5"/><path d="M14 1v4h-4M2 15v-4h4"/>
            </svg>
            Refresh
          </Button>
          <Button as="a" variant="secondary" size="sm" href={exportUrl} download>
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M8 2v9M5 8l3 3 3-3M2 13h12"/>
            </svg>
            Export CSV
          </Button>
        </div>
      </div>

      {team === 'TEST' && (
        <div style={{ padding: '10px 14px', background: 'var(--surface-2)', borderRadius: 'var(--r-lg)', border: '1px solid var(--border-1)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
          {!confirmWipe ? (
            <Button variant="danger" size="sm" onClick={() => setConfirmWipe(true)}>
              Wipe all rows
            </Button>
          ) : (
            <>
              <span className="text-danger text-sm font-medium">Delete ALL {total} rows from the TEST table? This cannot be undone.</span>
              <Button variant="danger" size="sm" loading={wipeMutation.isPending} onClick={() => wipeMutation.mutate()}>
                Yes, wipe everything
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmWipe(false)}>Cancel</Button>
            </>
          )}
        </div>
      )}

      <ErrorBanner error={error} title="Load error" />
      <ErrorBanner error={deleteMutation.error} title="Delete failed" />
      <ErrorBanner error={wipeMutation.error} title="Wipe failed" />

      {/* Selection actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-4" style={{ padding: '10px 14px', background: 'var(--surface-2)', borderRadius: 'var(--r-lg)', border: '1px solid var(--border-1)' }}>
          <Badge variant="accent" size="md">{selected.size} selected</Badge>
          {!confirmDelete ? (
            <Button variant="danger" size="sm" onClick={() => setConfirmDelete(true)}>
              Delete selected
            </Button>
          ) : (
            <>
              <span className="text-danger text-sm font-medium">Permanently delete {selected.size} source{selected.size !== 1 ? 's' : ''}?</span>
              <Button variant="danger" size="sm" loading={deleteMutation.isPending} onClick={() => deleteMutation.mutate(Array.from(selected))}>
                Confirm delete
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            </>
          )}
        </div>
      )}

      {isLoading ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <div className="empty-state">
          <svg className="empty-icon" viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="6" y="10" width="28" height="22" rx="3"/>
            <path d="M13 17h14M13 22h10"/>
          </svg>
          <p className="empty-text">No sources found</p>
          <p className="empty-sub">Try adjusting your filters</p>
        </div>
      ) : (
        <>
          {/* Count + page info */}
          <div className="flex items-center justify-between mb-3">
            <span className="row-count" style={{ margin: 0 }}>
              {total.toLocaleString()} total · showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)}
            </span>
            {totalPages > 1 && (
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
            )}
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>
                    <input type="checkbox" checked={selected.size === rows.length && rows.length > 0} onChange={toggleAll} />
                  </th>
                  <th>URL</th>
                  <th>Platform</th>
                  <th>Abuse Area</th>
                  <th>Sub Area</th>
                  <th>Relevancy</th>
                  <th>Notes</th>
                  <th>Metadata</th>
                  <th>Added</th>
                  <th>By</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggleRow(s.id)} />
                    </td>
                    <td className="cell-link" style={{ wordBreak: 'break-all' }}>
                      <a href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a>
                    </td>
                    <td>
                      {s.platform ? <Badge variant="info" size="sm">{s.platform}</Badge> : <span className="text-dim">—</span>}
                    </td>
                    <td className="text-sm">{s.abuse_area || <span className="text-dim">—</span>}</td>
                    <td className="text-sm">{s.sub_abuse_area || <span className="text-dim">—</span>}</td>
                    <td>
                      {s.relevancy ? <RelevancyBadge value={s.relevancy} /> : <span className="text-dim">—</span>}
                    </td>
                    <td className="cell-truncate text-sm" style={{ maxWidth: 200 }}>{s.notes || <span className="text-dim">—</span>}</td>
                    <td className="text-xs cell-mono" style={{ maxWidth: 140, position: 'relative', overflow: 'visible' }}>
                      {s.metadata && s.metadata !== '{}' ? (
                        <MetadataCell value={s.metadata} />
                      ) : <span className="text-dim">—</span>}
                    </td>
                    <td className="cell-mono text-xs text-dim">{s.added_at?.slice(0, 10)}</td>
                    <td className="text-sm text-muted">{s.added_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex justify-end mt-4">
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
            </div>
          )}
        </>
      )}
    </div>
  )
}

function MetadataCell({ value }: { value: string }) {
  const [open, setOpen] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  let parsed: Record<string, unknown>
  try {
    const v = typeof value === 'string' ? value : String(value)
    const sanitized = v.replace(/[\x00-\x1f]/g, (ch) => '\\u' + ch.charCodeAt(0).toString(16).padStart(4, '0'))
    parsed = JSON.parse(sanitized)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      return <span className="cell-truncate" style={{ maxWidth: 140, cursor: 'default' }}>{value}</span>
    }
  } catch {
    return <span className="cell-truncate" style={{ maxWidth: 140, cursor: 'default' }}>{value}</span>
  }

  const entries = Object.entries(parsed)
  const keyCount = entries.length
  const preview = `${keyCount} field${keyCount !== 1 ? 's' : ''}`

  return (
    <div style={{ position: 'relative' }}>
      <span
        onClick={() => setOpen(!open)}
        style={{
          cursor: 'pointer',
          display: 'inline-block',
          whiteSpace: 'nowrap',
          padding: '2px 6px',
          borderRadius: 'var(--r-sm)',
          background: 'var(--surface-2)',
          border: '1px solid var(--border-1)',
        }}
        title="Click to view metadata"
      >
        {preview}
      </span>
      {open && (
        <div
          ref={popoverRef}
          onWheel={(e) => {
            const el = e.currentTarget
            const atTop = el.scrollTop === 0 && e.deltaY < 0
            const atBottom = Math.abs(el.scrollTop + el.clientHeight - el.scrollHeight) < 1 && e.deltaY > 0
            if (!atTop && !atBottom) {
              e.stopPropagation()
            }
          }}
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            zIndex: 100,
            marginTop: 4,
            minWidth: 280,
            maxWidth: 420,
            maxHeight: 300,
            overflowY: 'auto',
            overscrollBehavior: 'contain',
            background: 'var(--surface-1)',
            border: '1px solid var(--border-2)',
            borderRadius: 'var(--r-lg)',
            boxShadow: '0 8px 24px rgba(0,0,0,.25)',
            padding: '12px 14px',
            fontFamily: 'var(--font-mono, monospace)',
            fontSize: 12,
            lineHeight: 1.6,
          }}
        >
          {entries.map(([key, val]) => (
            <div key={key} style={{ marginBottom: 4 }}>
              <span style={{ color: '#7cacf8', fontWeight: 600 }}>"{key}"</span>
              <span style={{ color: 'var(--t-secondary)' }}>: </span>
              <MetadataValue value={val} />
            </div>
          ))}
          {entries.length === 0 && <span className="text-dim">Empty object</span>}
        </div>
      )}
    </div>
  )
}

function MetadataValue({ value }: { value: unknown }) {
  if (value === null) return <span style={{ color: '#e06c75' }}>null</span>
  if (typeof value === 'boolean') return <span style={{ color: '#e06c75' }}>{String(value)}</span>
  if (typeof value === 'number') return <span style={{ color: '#d19a66' }}>{value}</span>
  if (typeof value === 'string') return <span style={{ color: '#98c379' }}>"{value}"</span>
  if (Array.isArray(value)) {
    return (
      <span style={{ color: '#98c379' }}>
        [{value.map((item, i) => (
          <span key={i}>{i > 0 && ', '}<MetadataValue value={item} /></span>
        ))}]
      </span>
    )
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    return (
      <span>
        {'{ '}
        {entries.map(([k, v], i) => (
          <span key={k}>
            {i > 0 && ', '}
            <span style={{ color: '#7cacf8', fontWeight: 600 }}>"{k}"</span>
            <span style={{ color: 'var(--t-secondary)' }}>: </span>
            <MetadataValue value={v} />
          </span>
        ))}
        {' }'}
      </span>
    )
  }
  return <span>{String(value)}</span>
}

function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  const maxVisible = 7
  const pages: (number | '…')[] = []

  if (totalPages <= maxVisible) {
    for (let i = 0; i < totalPages; i++) pages.push(i)
  } else {
    pages.push(0)
    if (page > 2) pages.push('…')
    for (let i = Math.max(1, page - 1); i <= Math.min(totalPages - 2, page + 1); i++) pages.push(i)
    if (page < totalPages - 3) pages.push('…')
    pages.push(totalPages - 1)
  }

  return (
    <div className="flex items-center gap-1">
      <button
        className="btn btn-ghost btn-sm"
        disabled={page === 0}
        onClick={() => onChange(page - 1)}
        style={{ padding: '5px 10px' }}
      >
        ←
      </button>
      {pages.map((p, i) =>
        p === '…' ? (
          <span key={`ellipsis-${i}`} className="text-dim" style={{ padding: '5px 6px', fontSize: 13 }}>…</span>
        ) : (
          <button
            key={p}
            onClick={() => onChange(p as number)}
            className={`btn btn-sm ${p === page ? 'btn-primary' : 'btn-ghost'}`}
            style={{ padding: '5px 10px', minWidth: 34 }}
          >
            {(p as number) + 1}
          </button>
        )
      )}
      <button
        className="btn btn-ghost btn-sm"
        disabled={page === totalPages - 1}
        onClick={() => onChange(page + 1)}
        style={{ padding: '5px 10px' }}
      >
        →
      </button>
    </div>
  )
}

function RelevancyBadge({ value }: { value: string }) {
  const lower = value.toLowerCase()
  if (lower.includes('high')) return <Badge variant="danger" size="sm">{value}</Badge>
  if (lower.includes('med')) return <Badge variant="warning" size="sm">{value}</Badge>
  return <Badge variant="neutral" size="sm">{value}</Badge>
}
