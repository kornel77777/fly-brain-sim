import { useEffect } from 'react'
import { Viewer } from './scene/Viewer'
import { showView, type ViewName } from './scene/views'
import { useStore } from './store'
import { ColorPanel } from './ui/ColorPanel'
import { NeuronPanel } from './ui/NeuronPanel'
import { Search } from './ui/Search'

const VIEWS: [ViewName, string][] = [
  ['front', 'Front'],
  ['back', 'Back'],
  ['top', 'Top'],
  ['side', 'Side'],
]

export default function App() {
  const load = useStore((s) => s.load)
  const status = useStore((s) => s.status)
  const error = useStore((s) => s.error)
  const meta = useStore((s) => s.meta)
  const focus = useStore((s) => s.focus)
  const setFocus = useStore((s) => s.setFocus)
  const select = useStore((s) => s.select)

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || (e.target as HTMLElement).tagName === 'INPUT') return
      select(null)
      setFocus(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [select, setFocus])

  return (
    <div className="app">
      <aside className="sidebar">
        <header>
          <h1>Fly Brain Viewer</h1>
          {meta && (
            <div className="muted small">
              FlyWire FAFB v783 · {meta.overview.n_neurons.toLocaleString()} neurons
            </div>
          )}
        </header>
        <Search />
        {focus && (
          <section className="focus row">
            <span className="grow small">
              Highlighting <strong>{focus.label}</strong>
            </span>
            <button className="link" onClick={() => setFocus(null)}>
              Clear
            </button>
          </section>
        )}
        <NeuronPanel />
        <ColorPanel />
        <footer className="small muted">
          Data: <a href="https://codex.flywire.ai" target="_blank" rel="noreferrer">FlyWire</a>{' '}
          (CC BY-NC 4.0). Dorkenwald et al. 2024; Schlegel et al. 2024.
        </footer>
      </aside>
      <main className="stage">
        <Viewer />
        <div className="views">
          {VIEWS.map(([name, label]) => (
            <button key={name} onClick={() => showView(name)}>
              {label}
            </button>
          ))}
        </div>
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
