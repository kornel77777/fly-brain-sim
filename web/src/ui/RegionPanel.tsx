import { regionInfo } from '../content'
import { useStore } from '../store'

const LIST_ROWS = 5

export function RegionPanel({ code }: { code: string }) {
  const regions = useStore((s) => s.regions)
  const selectRegion = useStore((s) => s.selectRegion)
  const setFocus = useStore((s) => s.setFocus)
  const attributes = useStore((s) => s.attributes)
  const r = regions?.regions.find((x) => x.name === code)
  const info = regionInfo(code)

  const highlightType = (cellType: string) => {
    const field = attributes?.fields.cell_type
    if (!field) return
    const code = field.categories.indexOf(cellType)
    const indices = field.codes.flatMap((c, i) => (c === code ? [i] : []))
    selectRegion(null)
    setFocus({ kind: 'set', label: `cell type ${cellType}`, indices })
  }

  return (
    <section>
      <div className="row">
        <span className="dot" style={{ background: info.group.color }} />
        <h2 className="grow">{info.name}</h2>
        <button className="link" onClick={() => selectRegion(null)} title="Clear (Esc)">
          Clear
        </button>
      </div>
      <div className="small muted">
        {info.group.label} · {code}
      </div>
      <p className="explain">{info.group.description}</p>
      {r && (
        <>
          <dl>
            <dt>Synapses</dt>
            <dd>{r.synapses.toLocaleString()}</dd>
            <dt>Neurons based here</dt>
            <dd>{r.home_neurons.toLocaleString()}</dd>
          </dl>
          <p className="small muted">
            Highlighted: example neurons whose synapses lie mostly in this region.
          </p>

          <h3>Main cell types</h3>
          <div className="chips">
            {r.top_cell_types.slice(0, LIST_ROWS).map((t) => (
              <button key={t.cell_type} className="chip" onClick={() => highlightType(t.cell_type)}>
                {t.cell_type}
              </button>
            ))}
          </div>

          <h3>Signals come from</h3>
          <FlowList flows={r.flows_in.slice(0, LIST_ROWS)} onSelect={selectRegion} />
          <h3>Signals go to</h3>
          <FlowList flows={r.flows_out.slice(0, LIST_ROWS)} onSelect={selectRegion} />
          <p className="small muted">
            Flow counts output synapses of neurons that receive input in one region and send
            output to the other.
          </p>
        </>
      )}
    </section>
  )
}

function FlowList(props: {
  flows: { region: string; synapses: number }[]
  onSelect: (code: string) => void
}) {
  const max = Math.max(1, ...props.flows.map((f) => f.synapses))
  return (
    <ul className="flows">
      {props.flows.map((f) => {
        const info = regionInfo(f.region)
        return (
          <li key={f.region}>
            <button className="result" onClick={() => props.onSelect(f.region)}>
              <span className="dot" style={{ background: info.group.color }} />
              <span className="grow">{info.name}</span>
              <span className="bar">
                <span style={{ width: `${(100 * f.synapses) / max}%` }} />
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
