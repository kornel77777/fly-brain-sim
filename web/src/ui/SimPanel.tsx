import { useEffect, useMemo } from 'react'
import type { SimTarget } from '../api'
import { SIM_HELP, regionInfo } from '../content'
import { activeBy, regionTotals } from '../sim'
import { useStore } from '../store'

const DURATIONS = [100, 300, 500, 1000]
const TOP_ROWS = 10
const REGION_ROWS = 8

export function SimPanel() {
  const sim = useStore((s) => s.sim)
  const loadSimPresets = useStore((s) => s.loadSimPresets)
  const setSimTarget = useStore((s) => s.setSimTarget)
  const setSim = useStore((s) => s.setSim)
  const runSim = useStore((s) => s.runSim)

  useEffect(() => {
    loadSimPresets()
  }, [loadSimPresets])

  const isTarget = (t: SimTarget) => JSON.stringify(t) === JSON.stringify(sim.target)

  return (
    <>
      <section>
        <p className="explain">{SIM_HELP.intro}</p>
        <details className="more">
          <summary className="small">How does the simulation work?</summary>
          <ul className="bullets">
            {SIM_HELP.how.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="small muted">{SIM_HELP.model}</p>
        </details>
      </section>

      <section>
        <h3>1. Choose what to stimulate</h3>
        <div className="cards">
          {(sim.presets ?? []).map((p) => {
            const target: SimTarget = { kind: 'preset', id: p.id }
            return (
              <button
                key={p.id}
                className={isTarget(target) ? 'card active' : 'card'}
                onClick={() => setSimTarget(target, p.label)}
              >
                <strong>{p.label}</strong>
                <span className="small muted"> · {p.n_neurons} neurons</span>
                <span className="small block">{p.description}</span>
              </button>
            )
          })}
        </div>
        <SelectionTargets isTarget={isTarget} />
      </section>

      <section>
        <h3>2. Settings</h3>
        <label className="row" title={SIM_HELP.rate}>
          <span>Rate</span>
          <input
            type="range"
            min={20}
            max={300}
            step={10}
            value={sim.rateHz}
            onChange={(e) => setSim({ rateHz: Number(e.target.value) })}
          />
          <span className="mono small">{sim.rateHz} Hz</span>
        </label>
        <label className="row">
          <span>Duration</span>
          <select
            value={sim.durationMs}
            onChange={(e) => setSim({ durationMs: Number(e.target.value) })}
          >
            {DURATIONS.map((d) => (
              <option key={d} value={d}>
                {d} ms
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary"
          disabled={!sim.target || sim.running}
          onClick={() => runSim()}
        >
          {sim.running
            ? 'Simulating…'
            : sim.target
              ? `Stimulate: ${sim.targetLabel}`
              : 'Choose something to stimulate'}
        </button>
      </section>

      {sim.result && <SimResults />}
    </>
  )
}

function SelectionTargets({ isTarget }: { isTarget: (t: SimTarget) => boolean }) {
  const selection = useStore((s) => s.selection)
  const region = useStore((s) => s.region)
  const setSimTarget = useStore((s) => s.setSimTarget)
  const cellType = selection?.info?.neuron.cell_type as string | undefined
  const side = selection?.info?.neuron.side as string | undefined

  const options: [SimTarget, string][] = []
  if (selection) {
    options.push([{ kind: 'neurons', root_ids: [selection.rootId] }, `This ${cellType ?? 'neuron'}`])
    if (cellType && side) {
      options.push([{ kind: 'cell_type', cell_type: cellType, side }, `All ${cellType} (${side})`])
    }
    if (cellType) options.push([{ kind: 'cell_type', cell_type: cellType }, `All ${cellType}`])
  }
  if (region) {
    options.push([{ kind: 'region', region }, `Neurons of ${regionInfo(region).name}`])
  }
  if (options.length === 0) {
    return (
      <p className="small muted">
        Or select a neuron or a brain region in the Explore tab to stimulate it here.
      </p>
    )
  }
  return (
    <>
      <p className="small muted">From your selection:</p>
      <div className="chips">
        {options.map(([t, label]) => (
          <button
            key={label}
            className={isTarget(t) ? 'chip active' : 'chip'}
            onClick={() => setSimTarget(t, label)}
          >
            {label}
          </button>
        ))}
      </div>
    </>
  )
}

function SimResults() {
  const result = useStore((s) => s.sim.result)!
  const bin = useStore((s) => s.sim.bin)
  const playing = useStore((s) => s.sim.playing)
  const setSim = useStore((s) => s.setSim)
  const select = useStore((s) => s.select)

  const current = Math.min(Math.floor(bin), result.n_bins - 1)
  const regions = useMemo(() => regionTotals(result).slice(0, REGION_ROWS), [result])
  const maxRegion = Math.max(1, ...regions.map((r) => r.spikes))
  const respondedNow = useMemo(() => activeBy(result, current), [result, current])
  const responded = result.active.length - result.stimulated.length

  return (
    <section>
      <h3>3. What happened</h3>
      <p>
        <strong>{result.label}</strong> at {result.rate_hz} Hz:{' '}
        {Math.max(0, responded).toLocaleString()} other neurons responded
        {' '}({result.n_spikes.toLocaleString()} spikes in {result.duration_ms} ms).
      </p>
      <div className="player">
        <button
          className="play"
          onClick={() =>
            setSim(bin >= result.n_bins - 1 ? { bin: 0, playing: true } : { playing: !playing })
          }
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <input
          type="range"
          min={0}
          max={result.n_bins - 1}
          step={1}
          value={current}
          onChange={(e) => setSim({ bin: Number(e.target.value), playing: false })}
          aria-label="Time"
        />
        <span className="mono small">{Math.round((current + 1) * result.bin_ms)} ms</span>
      </div>
      <p className="small muted">
        {respondedNow.toLocaleString()} neurons active so far. {SIM_HELP.reading}
      </p>
      {result.watch.length > 0 && (
        <>
          <h3>Key neurons</h3>
          <ul className="watch">
            {result.watch.map((w) => (
              <li key={w.label}>
                <span className={w.n_active > 0 ? 'dot on' : 'dot'} />
                <span className="grow">
                  {w.label}
                  <span className="small muted block">
                    {w.n_active > 0
                      ? `fired at ${w.rate_hz} Hz${w.n > 1 ? ' on average' : ''}, first spike after ${w.first_spike_ms} ms`
                      : 'stayed silent'}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {result.kenyon_cell_share > 0.2 && (
        <p className="note">{SIM_HELP.kenyon(result.kenyon_cell_share)}</p>
      )}
      {result.sampled && <p className="note">{SIM_HELP.sampled}</p>}

      <h3>Regions that lit up</h3>
      <ul className="flows">
        {regions.map((r) => {
          const info = regionInfo(r.region)
          return (
            <li key={r.region} className="legend-item static">
              <span className="dot" style={{ background: info.group.color }} />
              <span className="grow">{info.name}</span>
              <span className="bar">
                <span style={{ width: `${(100 * r.spikes) / maxRegion}%` }} />
              </span>
            </li>
          )
        })}
      </ul>

      <h3>Most active responding neurons</h3>
      <ul>
        {result.top.slice(0, TOP_ROWS).map((t) => (
          <li key={t.root_id}>
            <button className="result" onClick={() => select(t.root_id)} title="Open this neuron">
              <span className="grow">
                <strong>{t.cell_type ?? '—'}</strong>{' '}
                <span className="muted small">
                  {t.side} · first spike {t.first_spike_ms} ms
                </span>
              </span>
              <span className="mono small">{t.rate_hz} Hz</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
