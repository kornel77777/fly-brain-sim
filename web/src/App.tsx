import { useEffect } from 'react'
import { DETAIL_HELP, regionInfo } from './content'
import { Viewer } from './scene/Viewer'
import { showView, type ViewName } from './scene/views'
import { useStore, type Detail, type Tab } from './store'
import { ColorPanel } from './ui/ColorPanel'
import { Intro } from './ui/Intro'
import { NeuronPanel } from './ui/NeuronPanel'
import { RegionList } from './ui/RegionList'
import { RegionPanel } from './ui/RegionPanel'
import { Search } from './ui/Search'

const VIEWS: [ViewName, string][] = [
  ['front', 'Front'],
  ['top', 'Top'],
  ['side', 'Side'],
  ['back', 'Back'],
]

const DETAILS: [Detail, string][] = [
  ['regions', 'Regions'],
  ['sketch', 'Sketch'],
  ['all', 'All neurons'],
]

const TABS: [Tab, string][] = [
  ['explore', 'Explore'],
  ['regions', 'Brain regions'],
]

export default function App() {
  const load = useStore((s) => s.load)
  const status = useStore((s) => s.status)
  const error = useStore((s) => s.error)
  const tab = useStore((s) => s.tab)
  const setTab = useStore((s) => s.setTab)
  const detail = useStore((s) => s.detail)
  const setDetail = useStore((s) => s.setDetail)
  const hover = useStore((s) => s.hover)
  const selectRegion = useStore((s) => s.selectRegion)
  const setFocus = useStore((s) => s.setFocus)
  const select = useStore((s) => s.select)

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || (e.target as HTMLElement).tagName === 'INPUT') return
      select(null)
      selectRegion(null)
      setFocus(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [select, selectRegion, setFocus])

  return (
    <div className="app">
      <aside className="sidebar">
        <header>
          <h1>Fly Brain Viewer</h1>
          <Intro />
        </header>
        <nav className="tabs" role="tablist">
          {TABS.map(([id, label]) => (
            <button
              key={id}
              role="tab"
              aria-selected={tab === id}
              className={tab === id ? 'tab active' : 'tab'}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </nav>
        {tab === 'explore' && <ExploreTab />}
        {tab === 'regions' && <RegionList />}
        <footer className="small muted">
          Data: <a href="https://codex.flywire.ai" target="_blank" rel="noreferrer">FlyWire</a>{' '}
          (CC BY-NC 4.0). Dorkenwald et al. 2024; Schlegel et al. 2024.
        </footer>
      </aside>
      <main className="stage">
        <Viewer />
        <div className="toolbar">
          <div className="segmented" role="group" aria-label="Level of detail">
            {DETAILS.map(([id, label]) => (
              <button
                key={id}
                className={detail === id ? 'active' : ''}
                onClick={() => setDetail(id)}
                title={DETAIL_HELP[id]}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="segmented" role="group" aria-label="Camera">
            {VIEWS.map(([name, label]) => (
              <button key={name} onClick={() => showView(name)}>
                {label}
              </button>
            ))}
          </div>
        </div>
        {hover && (
          <div className="tooltip" style={{ left: hover.x + 14, top: hover.y + 14 }}>
            {regionInfo(hover.region).name}
          </div>
        )}
        {status && <div className="overlay">{status}</div>}
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
      </main>
    </div>
  )
}

function ExploreTab() {
  const region = useStore((s) => s.region)
  const selection = useStore((s) => s.selection)
  const focus = useStore((s) => s.focus)
  const setFocus = useStore((s) => s.setFocus)
  return (
    <>
      <Search />
      {focus && !selection && !region && (
        <section className="focus row">
          <span className="grow small">
            Highlighting <strong>{focus.label}</strong>
          </span>
          <button className="link" onClick={() => setFocus(null)}>
            Clear
          </button>
        </section>
      )}
      {region && <RegionPanel code={region} />}
      <NeuronPanel />
      {!region && !selection && (
        <section>
          <p className="small muted">
            Click a brain region or a neuron, or search for a cell type such as{' '}
            <em>EPG</em> (compass neurons) or <em>KCg-m</em> (Kenyon cells).
          </p>
        </section>
      )}
      <ColorPanel />
    </>
  )
}
