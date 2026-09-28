import { useMemo, useState } from 'react'
import { categoryColors, rgbCss } from '../colors'
import { useStore } from '../store'

const LEGEND_ROWS = 12

const LABELS: Record<string, string> = {
  super_class: 'Super class',
  flow: 'Flow',
  class: 'Class',
  sub_class: 'Sub class',
  nt_type: 'Neurotransmitter',
  side: 'Side',
  ito_lee_hemilineage: 'Hemilineage',
  neuropil_group: 'Neuropil group',
  cell_type: 'Cell type',
}

export function ColorPanel() {
  const meta = useStore((s) => s.meta)
  const attributes = useStore((s) => s.attributes)
  const colorField = useStore((s) => s.colorField)
  const setColorField = useStore((s) => s.setColorField)
  const focus = useStore((s) => s.focus)
  const setFocus = useStore((s) => s.setFocus)
  const select = useStore((s) => s.select)
  const opacity = useStore((s) => s.opacity)
  const setOpacity = useStore((s) => s.setOpacity)
  const [expanded, setExpanded] = useState(false)

  const field = attributes?.fields[colorField]
  const colors = useMemo(
    () => (field ? categoryColors(colorField, field.categories) : []),
    [colorField, field],
  )
  if (!meta || !field) return null

  const rows = expanded ? field.categories.length : Math.min(LEGEND_ROWS, field.categories.length)
  const missing = field.codes.filter((c) => c < 0).length

  return (
    <section>
      <h2>Color</h2>
      <label className="row">
        <span>By</span>
        <select value={colorField} onChange={(e) => setColorField(e.target.value)}>
          {meta.color_fields.map((f) => (
            <option key={f} value={f}>
              {LABELS[f] ?? f}
            </option>
          ))}
        </select>
      </label>
      <label className="row">
        <span>Opacity</span>
        <input
          type="range"
          min={0.02}
          max={1}
          step={0.01}
          value={opacity}
          onChange={(e) => setOpacity(Number(e.target.value))}
        />
      </label>
      <ul className="legend">
        {field.categories.slice(0, rows).map((cat, code) => {
          const active = focus?.kind === 'category' && focus.field === colorField && focus.code === code
          return (
            <li key={cat}>
              <button
                className={active ? 'legend-item active' : 'legend-item'}
                onClick={() => {
                  select(null)
                  setFocus(active ? null : { kind: 'category', field: colorField, code, label: cat })
                }}
                title="Highlight this category"
              >
                <span className="dot" style={{ background: rgbCss(colors[code]) }} />
                <span className="grow">{cat}</span>
                <span className="small muted">{field.counts[code].toLocaleString()}</span>
              </button>
            </li>
          )
        })}
        {missing > 0 && (
          <li className="legend-item static">
            <span className="dot" style={{ background: 'rgb(85,85,85)' }} />
            <span className="grow muted">(missing)</span>
            <span className="small muted">{missing.toLocaleString()}</span>
          </li>
        )}
      </ul>
      {field.categories.length > LEGEND_ROWS && (
        <button className="link" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Show fewer' : `Show all ${field.categories.length.toLocaleString()}`}
        </button>
      )}
    </section>
  )
}
