import { useState } from 'react'

const UNITS = [
  { label: 'Minutes', value: 'minutes', factor: 1 },
  { label: 'Hours', value: 'hours', factor: 60 },
  { label: 'Days', value: 'days', factor: 1440 },
  { label: 'Weeks', value: 'weeks', factor: 10080 },
  { label: 'Months', value: 'months', factor: 43200 },
]

function bestUnit(m: number) {
  if (m >= 43200 && m % 43200 === 0) return 'months'
  if (m >= 10080 && m % 10080 === 0) return 'weeks'
  if (m >= 1440 && m % 1440 === 0) return 'days'
  if (m >= 60 && m % 60 === 0) return 'hours'
  return 'minutes'
}

export function IntervalPicker({ minutes, onChange }: { minutes: number; onChange: (m: number) => void }) {
  const [unit, setUnit] = useState(() => bestUnit(minutes))
  const factor = UNITS.find((u) => u.value === unit)!.factor
  const display = Math.max(1, Math.round(minutes / factor))

  function handleValueChange(val: number) {
    onChange(Math.max(5, val * factor))
  }
  function handleUnitChange(u: string) {
    setUnit(u)
    const f = UNITS.find((iu) => iu.value === u)!.factor
    onChange(Math.max(5, display * f))
  }

  return (
    <div className="flex gap-2 items-end">
      <div style={{ width: 80 }}>
        <label className="form-label">Every</label>
        <input
          type="number"
          className="form-input"
          min={1}
          value={display}
          onChange={(e) => handleValueChange(Math.max(1, Number(e.target.value) || 1))}
        />
      </div>
      <div style={{ width: 120 }}>
        <label className="form-label">&nbsp;</label>
        <select className="form-select" value={unit} onChange={(e) => handleUnitChange(e.target.value)}>
          {UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
        </select>
      </div>
    </div>
  )
}
