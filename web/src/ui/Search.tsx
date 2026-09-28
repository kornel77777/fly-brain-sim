import { useEffect, useState } from 'react'
import { api, type SearchResult } from '../api'
import { categoryColors, rgbCss } from '../colors'
import { useStore } from '../store'

const DEBOUNCE_MS = 250

export function Search() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<{ total: number; results: SearchResult[] } | null>(null)
  const select = useStore((s) => s.select)
  const setFocus = useStore((s) => s.setFocus)
  const attributes = useStore((s) => s.attributes)
  const fail = useStore((s) => s.fail)

  useEffect(() => {
    const query = q.trim()
    if (!query) return
    let stale = false
    const t = setTimeout(() => {
      api
        .search(query)
        .then((r) => !stale && setResults(r))
        .catch(fail)
    }, DEBOUNCE_MS)
    return () => {
      stale = true
      clearTimeout(t)
    }
  }, [q, fail])

  // If the query is exactly a cell type, offer to highlight all of them.
  const cellTypes = attributes?.fields.cell_type
  const typeCode = cellTypes ? cellTypes.categories.findIndex((c) => c.toLowerCase() === q.trim().toLowerCase()) : -1

  const highlightType = () => {
    if (!cellTypes || typeCode < 0) return
    const indices = cellTypes.codes.flatMap((c, i) => (c === typeCode ? [i] : []))
    select(null)
    setFocus({ kind: 'set', label: `cell type ${cellTypes.categories[typeCode]}`, indices })
  }

  return (
    <section>
      <input
        type="search"
        placeholder="Search cell type, name, label or root ID"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label="Search neurons"
      />
      {results && q.trim() && (
        <div className="results">
          <div className="muted small">
            {results.total.toLocaleString()} match{results.total === 1 ? '' : 'es'}
            {results.total > results.results.length && `, showing ${results.results.length}`}
          </div>
          {typeCode >= 0 && cellTypes && (
            <button className="link" onClick={highlightType}>
              Highlight all {cellTypes.counts[typeCode].toLocaleString()} {cellTypes.categories[typeCode]}
            </button>
          )}
          <ul>
            {results.results.map((r) => (
              <li key={r.root_id}>
                <button className="result" onClick={() => select(r.root_id)}>
                  <SuperClassDot superClass={r.super_class} />
                  <span className="grow">
                    <strong>{r.cell_type ?? '—'}</strong> <span className="muted">{r.name}</span>
                    {r.matched_label && <span className="small muted block">“{r.matched_label}”</span>}
                  </span>
                  <span className="small muted">{r.side}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function SuperClassDot({ superClass }: { superClass: string | null }) {
  const field = useStore((s) => s.attributes?.fields.super_class)
  if (!field || !superClass) return <span className="dot" />
  const i = field.categories.indexOf(superClass)
  const color = categoryColors('super_class', field.categories)[i]
  return <span className="dot" style={{ background: rgbCss(color) }} title={superClass} />
}
