import { useState } from 'react'
import { Button } from '../ui/Button'
import type { GoogleDorkingConfig } from '../../api/pipelines'

interface Props {
  onSubmit: (config: GoogleDorkingConfig) => void
  loading: boolean
}

function parseLines(raw: string): string[] {
  return raw
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
}

export function GoogleDorkingForm({ onSubmit, loading }: Props) {
  const [keywords, setKeywords] = useState('')
  const [sites, setSites] = useState('')
  const [clients, setClients] = useState('')
  const [ruleOut, setRuleOut] = useState('')
  const [timeframe, setTimeframe] = useState<7 | 30 | 90 | 365>(30)
  const [numResults, setNumResults] = useState(100)
  const [verbatim, setVerbatim] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [error, setError] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const kws = parseLines(keywords)
    if (!kws.length) {
      setError('At least one keyword is required.')
      return
    }
    setError('')
    onSubmit({
      keywords: kws,
      sites: parseLines(sites),
      clients: parseLines(clients),
      rule_out: parseLines(ruleOut),
      timeframe,
      num_of_results: numResults,
      verbatim,
    })
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Keywords */}
      <div className="form-field">
        <label htmlFor="gd-keywords" className="form-label">
          Keywords <span style={{ color: 'var(--danger)' }}>*</span>
        </label>
        <p className="form-hint">One query per line. Commas within a line are part of the same query phrase.</p>
        <textarea
          id="gd-keywords"
          className="form-textarea"
          rows={5}
          placeholder={"leaked photos\nconfidential documents\nprivate videos"}
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          disabled={loading}
        />
        {parseLines(keywords).length > 0 && (
          <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {parseLines(keywords).map((kw) => (
              <span key={kw} className="badge badge-accent badge-sm">{kw}</span>
            ))}
          </div>
        )}
        {error && <p style={{ color: 'var(--danger)', fontSize: 12, marginTop: 4 }}>{error}</p>}
      </div>

      {/* Sites */}
      <div className="form-field">
        <label htmlFor="gd-sites" className="form-label">Sites to search</label>
        <p className="form-hint">Restrict results to these domains. One per line or comma-separated. Leave empty for global search.</p>
        <textarea
          id="gd-sites"
          className="form-textarea"
          rows={3}
          placeholder={"telegram.org\nt.me"}
          value={sites}
          onChange={(e) => setSites(e.target.value)}
          disabled={loading}
        />
      </div>

      {/* Row: Timeframe + Num results */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="form-field">
          <label className="form-label">Timeframe</label>
          <select
            className="form-select"
            value={timeframe}
            onChange={(e) => setTimeframe(Number(e.target.value) as 7 | 30 | 90 | 365)}
            disabled={loading}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
        </div>
        <div className="form-field">
          <label className="form-label">Number of results</label>
          <input
            type="number"
            className="form-input"
            min={1}
            max={1000}
            value={numResults}
            onChange={(e) => setNumResults(Number(e.target.value))}
            disabled={loading}
          />
        </div>
      </div>

      {/* Verbatim toggle */}
      <div className="form-field" style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
        <input
          type="checkbox"
          id="verbatim"
          checked={verbatim}
          onChange={(e) => setVerbatim(e.target.checked)}
          disabled={loading}
          style={{ width: 15, height: 15, cursor: 'pointer' }}
        />
        <label htmlFor="verbatim" style={{ cursor: 'pointer', margin: 0 }}>
          Verbatim matching (exact phrase)
        </label>
      </div>

      {/* Advanced */}
      <div>
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          style={{ background: 'none', border: 'none', color: 'var(--t2)', cursor: 'pointer', fontSize: 12, padding: 0, display: 'flex', alignItems: 'center', gap: 4 }}
        >
          <span style={{ transform: showAdvanced ? 'rotate(90deg)' : 'none', display: 'inline-block', transition: 'transform 0.15s' }}>▶</span>
          Advanced options
        </button>

        {showAdvanced && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 14 }}>
            <div className="form-field">
              <label className="form-label">Client / brand terms</label>
              <p className="form-hint">Added to every query. One per line or comma-separated.</p>
              <textarea
                className="form-textarea"
                rows={2}
                placeholder="ActiveFence"
                value={clients}
                onChange={(e) => setClients(e.target.value)}
                disabled={loading}
              />
            </div>
            <div className="form-field">
              <label className="form-label">Terms to exclude</label>
              <p className="form-hint">Auto-prefixed with minus. One per line or comma-separated.</p>
              <textarea
                className="form-textarea"
                rows={2}
                placeholder="news, blog"
                value={ruleOut}
                onChange={(e) => setRuleOut(e.target.value)}
                disabled={loading}
              />
            </div>
          </div>
        )}
      </div>

      <div>
        <Button type="submit" variant="primary" loading={loading} disabled={loading}>
          {loading ? 'Starting pipeline…' : 'Run Google Dorking'}
        </Button>
      </div>
    </form>
  )
}
