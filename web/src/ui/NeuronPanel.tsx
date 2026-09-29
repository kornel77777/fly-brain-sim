import type { Direction, Partner } from '../api'
import { BOTH, DOWNSTREAM, UPSTREAM, rgbCss } from '../colors'
import { FIELD_HELP, regionInfo } from '../content'
import { useStore, type SynapseDirection } from '../store'

const PARTNER_ROWS = 8
const NT_FIELDS = ['ach_avg', 'gaba_avg', 'glut_avg', 'da_avg', 'ser_avg', 'oct_avg'] as const

export function NeuronPanel() {
  const selection = useStore((s) => s.selection)
  const select = useStore((s) => s.select)
  const minSyn = useStore((s) => s.minSyn)
  const setMinSyn = useStore((s) => s.setMinSyn)
  const showPartners = useStore((s) => s.showPartners)
  const togglePartners = useStore((s) => s.togglePartners)
  const showSynapses = useStore((s) => s.showSynapses)
  const toggleSynapses = useStore((s) => s.toggleSynapses)
  const selectRegion = useStore((s) => s.selectRegion)
  const hasSynapses = useStore((s) => s.meta?.has_synapses ?? false)

  if (!selection) return null
  const { info, partners, synapses } = selection
  const n = info?.neuron
  const a = info?.annotations

  return (
    <section>
      <div className="row">
        <h2 className="grow">{(n?.cell_type as string) ?? 'Neuron'}</h2>
        <button className="link" onClick={() => select(null)} title="Clear selection (Esc)">
          Clear
        </button>
      </div>
      <div className="mono small">
        {selection.rootId}{' '}
        <button className="link" onClick={() => navigator.clipboard.writeText(selection.rootId)}>
          copy
        </button>
      </div>
      {!info && <p className="muted small">Loading…</p>}
      {n && (
        <>
          <p className="explain">
            {FIELD_HELP.super_class.values?.[n.super_class as string] ?? ''}{' '}
            {n.nt_type
              ? FIELD_HELP.nt_type.values?.[n.nt_type as string]
              : 'Its neurotransmitter could not be predicted confidently.'}
          </p>
          <dl>
            {n.home_neuropil && (
              <>
                <dt>Mostly in</dt>
                <dd>
                  <button className="link" onClick={() => selectRegion(n.home_neuropil as string)}>
                    {regionInfo(n.home_neuropil as string).name}
                  </button>
                </dd>
              </>
            )}
            <Item k="Receives" v={`${info.input_synapses.toLocaleString()} synapses`} />
            <Item k="Sends" v={`${info.output_synapses.toLocaleString()} synapses`} />
          </dl>
          <details className="more">
            <summary className="small muted">More details</summary>
            <dl>
              <Item k="Name" v={n.name} />
              <Item k="Super class" v={n.super_class} />
              <Item k="Class" v={[n.class, n.sub_class].filter(Boolean).join(' / ') || null} />
              <Item k="Hemibrain type" v={a?.hemibrain_type ?? null} />
              <Item k="Side" v={n.side} />
              <Item k="Hemilineage" v={n.ito_lee_hemilineage} />
              <Item
                k="Neurotransmitter"
                v={n.nt_type ? `${n.nt_type} (${Number(n.nt_type_score).toFixed(2)})` : 'unassigned'}
              />
              <Item
                k="Shiu model"
                v={info.shiu_index !== null ? `index ${info.shiu_index}` : 'not in model'}
              />
            </dl>
          </details>
        </>
      )}
      {n && <NtBar neuron={n} />}

      <h3>Connectivity</h3>
      <label className="row">
        <span>Min synapses</span>
        <input
          type="range"
          min={1}
          max={50}
          value={minSyn}
          onChange={(e) => setMinSyn(Number(e.target.value))}
        />
        <span className="mono small">{minSyn}</span>
      </label>
      {(['upstream', 'downstream'] as Direction[]).map((d) => (
        <PartnerList
          key={d}
          direction={d}
          partners={partners[d]}
          shown={showPartners[d]}
          onToggle={() => togglePartners(d)}
          onSelect={select}
        />
      ))}
      <div className="small muted legend-inline">
        <span className="dot" style={{ background: rgbCss(BOTH) }} /> both directions
      </div>

      <h3>Synapses</h3>
      {!hasSynapses && <p className="muted small">Synapse DB not built (scripts/build_synapses.py).</p>}
      {hasSynapses &&
        (['outgoing', 'incoming'] as SynapseDirection[]).map((d) => (
          <label key={d} className="row">
            <input type="checkbox" checked={showSynapses[d]} onChange={() => toggleSynapses(d)} />
            <span className="dot" style={{ background: rgbCss(d === 'outgoing' ? DOWNSTREAM : UPSTREAM) }} />
            <span className="grow">{d === 'outgoing' ? 'Output (presynaptic)' : 'Input (postsynaptic)'}</span>
            <span className="small muted">
              {synapses[d] ? synapses[d]!.n.toLocaleString() : showSynapses[d] ? '…' : ''}
            </span>
          </label>
        ))}
    </section>
  )
}

function Item({ k, v }: { k: string; v: string | number | null | undefined }) {
  if (v === null || v === undefined || v === '') return null
  return (
    <>
      <dt>{k}</dt>
      <dd>{String(v)}</dd>
    </>
  )
}

function NtBar({ neuron }: { neuron: Record<string, string | number | null> }) {
  const colors: Record<string, string> = {
    ach_avg: '#ff9f40',
    gaba_avg: '#5ab4ff',
    glut_avg: '#b18cff',
    da_avg: '#ffd54f',
    ser_avg: '#4dd0e1',
    oct_avg: '#f06292',
  }
  const total = NT_FIELDS.reduce((s, f) => s + Number(neuron[f] ?? 0), 0)
  if (total <= 0) return null
  return (
    <div className="ntbar" title="Predicted neurotransmitter probabilities">
      {NT_FIELDS.map((f) => {
        const v = Number(neuron[f] ?? 0)
        if (v <= 0) return null
        return (
          <span
            key={f}
            style={{ width: `${(100 * v) / total}%`, background: colors[f] }}
            title={`${f.replace('_avg', '').toUpperCase()} ${v.toFixed(2)}`}
          />
        )
      })}
    </div>
  )
}

function PartnerList(props: {
  direction: Direction
  partners: Partner[] | null
  shown: boolean
  onToggle: () => void
  onSelect: (rootId: string) => void
}) {
  const { direction, partners, shown, onToggle, onSelect } = props
  const color = direction === 'upstream' ? UPSTREAM : DOWNSTREAM
  const total = partners?.reduce((s, p) => s + p.syn_count, 0) ?? 0
  return (
    <div className="partners">
      <label className="row">
        <input type="checkbox" checked={shown} onChange={onToggle} />
        <span className="dot" style={{ background: rgbCss(color) }} />
        <span className="grow">{direction === 'upstream' ? 'Upstream (inputs)' : 'Downstream (outputs)'}</span>
        <span className="small muted">
          {partners ? `${partners.length.toLocaleString()} · ${total.toLocaleString()} syn` : '…'}
        </span>
      </label>
      {partners && partners.length > 0 && (
        <ul>
          {partners.slice(0, PARTNER_ROWS).map((p) => (
            <li key={p.root_id}>
              <button className="result" onClick={() => onSelect(p.root_id)}>
                <span className="grow">
                  <strong>{p.cell_type ?? '—'}</strong> <span className="muted small">{p.side}</span>
                </span>
                <span className="mono small">{p.syn_count}</span>
              </button>
            </li>
          ))}
          {partners.length > PARTNER_ROWS && (
            <li className="small muted">+ {(partners.length - PARTNER_ROWS).toLocaleString()} more</li>
          )}
        </ul>
      )}
    </div>
  )
}
