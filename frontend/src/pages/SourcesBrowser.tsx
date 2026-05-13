import { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { Source, SourceFilters } from '../api/sources'
import { deleteSources, exportSourcesUrl, getFilterOptions, listSources, updateSource, wipeAllSources } from '../api/sources'
import { ErrorBanner } from '../components/shared/ErrorBanner'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
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
  const [editingSource, setEditingSource] = useState<Source | null>(null)

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
          <MultiSelect
            label="Platform"
            options={filterOptions?.platforms ?? []}
            value={filters.platform}
            onChange={(v) => setFilter('platform', v)}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <MultiSelect
            label="Abuse Area"
            options={filterOptions?.abuse_areas ?? []}
            value={filters.abuse_area}
            onChange={(v) => setFilter('abuse_area', v)}
          />
        </div>
        <div style={{ minWidth: 160 }}>
          <MultiSelect
            label="Sub Abuse Area"
            options={filterOptions?.sub_abuse_areas ?? []}
            value={filters.sub_abuse_area}
            onChange={(v) => setFilter('sub_abuse_area', v)}
          />
        </div>
        <div style={{ minWidth: 140 }}>
          <MultiSelect
            label="Relevancy"
            options={filterOptions?.relevancies ?? []}
            value={filters.relevancy}
            onChange={(v) => setFilter('relevancy', v)}
          />
        </div>
        <div style={{ minWidth: 150 }}>
          <MultiSelect
            label="Added By"
            options={filterOptions?.added_by ?? []}
            value={filters.added_by}
            onChange={(v) => setFilter('added_by', v)}
          />
        </div>
        <div style={{ minWidth: 200, flex: 1 }}>
          <Input
            label="Search"
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
          <Button variant="ghost" size="sm" onClick={() => { qc.refetchQueries({ queryKey: ['sources', team] }); qc.refetchQueries({ queryKey: ['filter-options', team] }) }}>
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
                  <th style={{ width: 40 }}></th>
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
                    <td>
                      <button
                        onClick={() => setEditingSource(s)}
                        title="Edit"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--t-secondary)', padding: '2px 4px', borderRadius: 'var(--r-sm)', lineHeight: 1 }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--t-accent)')}
                        onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--t-secondary)')}
                      >
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11.5 2.5a1.414 1.414 0 0 1 2 2L5 13l-3 1 1-3 8.5-8.5z"/>
                        </svg>
                      </button>
                    </td>
                    <td className="cell-link" style={{ wordBreak: 'break-all' }}>
                      <a href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a>
                    </td>
                    <td>
                      {s.platform ? <Badge variant="info" size="sm">{s.platform}</Badge> : <span className="text-dim">—</span>}
                    </td>
                    <td className="text-sm">{s.abuse_area ? <CommaBadges value={s.abuse_area} /> : <span className="text-dim">—</span>}</td>
                    <td className="text-sm">{s.sub_abuse_area ? <CommaBadges value={s.sub_abuse_area} /> : <span className="text-dim">—</span>}</td>
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
                    <td className="text-sm text-muted">{formatAddedBy(s.added_by)}</td>
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

      {editingSource && (
        <EditModal
          source={editingSource}
          team={team}
          filterOptions={filterOptions}
          onClose={() => setEditingSource(null)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ['sources', team] })
            setEditingSource(null)
          }}
        />
      )}
    </div>
  )
}

function EditModal({
  source,
  team,
  filterOptions,
  onClose,
  onSaved,
}: {
  source: Source
  team: string
  filterOptions?: { platforms: string[]; abuse_areas: string[]; sub_abuse_areas: string[]; relevancies: string[] }
  onClose: () => void
  onSaved: () => void
}) {
  const [platform, setPlatform] = useState(source.platform ?? '')
  const [abuseArea, setAbuseArea] = useState(source.abuse_area ?? '')
  const [subAbuseArea, setSubAbuseArea] = useState(source.sub_abuse_area ?? '')
  const [relevancy, setRelevancy] = useState(source.relevancy ?? '')
  const [notes, setNotes] = useState(source.notes ?? '')

  const mutation = useMutation({
    mutationFn: () => updateSource(team, source.id, { platform, abuse_area: abuseArea, sub_abuse_area: subAbuseArea, relevancy, notes }),
    onSuccess: onSaved,
  })

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const fieldStyle: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4 }
  const labelStyle: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: 'var(--t-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }
  const selectStyle: React.CSSProperties = {
    background: 'var(--surface-2)',
    border: '1px solid var(--border-2)',
    borderRadius: 'var(--r-md)',
    color: 'var(--t-primary)',
    padding: '7px 10px',
    fontSize: 14,
    outline: 'none',
    width: '100%',
  }
  const inputStyle: React.CSSProperties = { ...selectStyle }

  const platforms = filterOptions?.platforms?.length ? filterOptions.platforms : ['Telegram', 'Twitter/X', 'TikTok', 'Instagram', 'YouTube', 'Facebook', 'Other']
  const relevancies = filterOptions?.relevancies?.length ? filterOptions.relevancies : ['Yes', 'No', 'Low', 'Medium', 'High']

  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,.55)', backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border-2)',
        borderRadius: 'var(--r-xl)',
        boxShadow: '0 16px 48px rgba(0,0,0,.4)',
        padding: '28px 32px',
        width: '100%',
        maxWidth: 520,
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Edit Source</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--t-secondary)', fontSize: 20, lineHeight: 1, padding: 4 }}>✕</button>
        </div>

        <div style={{ fontSize: 13, color: 'var(--t-secondary)', wordBreak: 'break-all', padding: '8px 12px', background: 'var(--surface-2)', borderRadius: 'var(--r-md)', border: '1px solid var(--border-1)' }}>
          {source.url}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={fieldStyle}>
            <label style={labelStyle}>Platform</label>
            <select value={platform} onChange={(e) => setPlatform(e.target.value)} style={selectStyle}>
              <option value="">— none —</option>
              {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
              {platform && !platforms.includes(platform) && <option value={platform}>{platform}</option>}
            </select>
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Relevancy</label>
            <select value={relevancy} onChange={(e) => setRelevancy(e.target.value)} style={selectStyle}>
              <option value="">— none —</option>
              {relevancies.map((r) => <option key={r} value={r}>{r}</option>)}
              {relevancy && !relevancies.includes(relevancy) && <option value={relevancy}>{relevancy}</option>}
            </select>
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Abuse Area</label>
            <input value={abuseArea} onChange={(e) => setAbuseArea(e.target.value)} style={inputStyle} placeholder="e.g. Hate Speech" list="abuse-area-list" />
            <datalist id="abuse-area-list">
              {(filterOptions?.abuse_areas ?? []).map((a) => <option key={a} value={a} />)}
            </datalist>
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Sub Abuse Area</label>
            <input value={subAbuseArea} onChange={(e) => setSubAbuseArea(e.target.value)} style={inputStyle} placeholder="e.g. Antisemitism" list="sub-abuse-area-list" />
            <datalist id="sub-abuse-area-list">
              {(filterOptions?.sub_abuse_areas ?? []).map((a) => <option key={a} value={a} />)}
            </datalist>
          </div>
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
            placeholder="Optional notes…"
          />
        </div>

        <ErrorBanner error={mutation.error} title="Save failed" />

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Save changes
          </Button>
        </div>
      </div>
    </div>
  )
}

function formatAddedBy(val?: string): string {
  if (!val) return '—'
  if (/^\d+@\d+$/.test(val)) return 'auto-sync'
  if (val.includes('@')) return val.split('@')[0]
  return val
}

function CommaBadges({ value }: { value: string }) {
  const parts = value.split(',').map((v) => v.trim()).filter(Boolean)
  if (parts.length <= 1) return <>{value}</>
  return (
    <span style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {parts.map((p, i) => (
        <Badge key={i} variant="neutral" size="sm">{p}</Badge>
      ))}
    </span>
  )
}

function MultiSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: string[]
  value: string | undefined
  onChange: (v: string) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const selected = value ? value.split(',').map((v) => v.trim()).filter(Boolean) : []

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  function toggle(opt: string) {
    const next = selected.includes(opt) ? selected.filter((s) => s !== opt) : [...selected, opt]
    onChange(next.join(','))
  }

  function remove(opt: string) {
    onChange(selected.filter((s) => s !== opt).join(','))
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--t3)', marginBottom: 4 }}>{label}</label>
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 4,
          alignItems: 'center',
          minHeight: 36,
          padding: '4px 8px',
          background: 'var(--surface-3)',
          border: '1px solid var(--border-2)',
          borderRadius: 'var(--r-md)',
          cursor: 'pointer',
          fontSize: 13,
        }}
      >
        {selected.length === 0 && <span style={{ color: 'var(--t3)' }}>All</span>}
        {selected.map((s) => (
          <span
            key={s}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              padding: '1px 6px',
              borderRadius: 'var(--r-sm)',
              background: 'var(--accent-dim)',
              border: '1px solid var(--accent-border)',
              color: 'var(--t-accent)',
              fontSize: 12,
              lineHeight: '18px',
            }}
          >
            {s}
            <span
              onClick={(e) => { e.stopPropagation(); remove(s) }}
              style={{ cursor: 'pointer', fontSize: 14, lineHeight: 1, opacity: 0.7 }}
            >
              ×
            </span>
          </span>
        ))}
      </div>
      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 50,
            marginTop: 4,
            maxHeight: 240,
            overflowY: 'auto',
            background: 'var(--surface-1)',
            border: '1px solid var(--border-2)',
            borderRadius: 'var(--r-md)',
            boxShadow: '0 8px 24px rgba(0,0,0,.25)',
            padding: 4,
          }}
        >
          {options.map((opt) => {
            const checked = selected.includes(opt)
            return (
              <label
                key={opt}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 8px',
                  borderRadius: 'var(--r-sm)',
                  cursor: 'pointer',
                  fontSize: 13,
                  color: checked ? 'var(--t-accent)' : 'var(--t2)',
                  background: checked ? 'var(--accent-dim)' : 'transparent',
                }}
                onMouseEnter={(e) => { if (!checked) (e.currentTarget.style.background = 'var(--surface-2)') }}
                onMouseLeave={(e) => { if (!checked) (e.currentTarget.style.background = 'transparent') }}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(opt)}
                  style={{ accentColor: 'var(--t-accent)' }}
                />
                {opt}
              </label>
            )
          })}
          {options.length === 0 && <div style={{ padding: '8px', color: 'var(--t3)', fontSize: 13 }}>No options</div>}
        </div>
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
