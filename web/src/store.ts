import { create } from 'zustand'
import {
  api,
  type Attributes,
  type Direction,
  type Meta,
  type NeuronInfo,
  type Overview,
  type Partner,
} from './api'
import type { SkeletonData, SynapseData } from './decode'

export type Focus =
  | { kind: 'category'; field: string; code: number; label: string }
  | { kind: 'set'; label: string; indices: number[] }

export type SynapseDirection = 'outgoing' | 'incoming'

interface Selection {
  rootId: string
  index: number
  info: NeuronInfo | null
  skeleton: SkeletonData | null
  partners: Record<Direction, Partner[] | null>
  synapses: Record<SynapseDirection, SynapseData | null>
}

interface State {
  status: string | null // loading message; null once ready
  error: string | null
  meta: Meta | null
  attributes: Attributes | null
  overview: Overview | null

  colorField: string
  opacity: number
  contextBrightness: number // 0..1 brightness of neurons outside a highlight; 0 hides them
  focus: Focus | null

  selection: Selection | null
  minSyn: number
  showPartners: Record<Direction, boolean>
  showSynapses: Record<SynapseDirection, boolean>

  load: () => Promise<void>
  setColorField: (field: string) => void
  setOpacity: (v: number) => void
  setContextBrightness: (v: number) => void
  setFocus: (f: Focus | null) => void
  select: (rootId: string | null) => Promise<void>
  setMinSyn: (v: number) => void
  togglePartners: (d: Direction) => void
  toggleSynapses: (d: SynapseDirection) => void
  fail: (e: unknown) => void
}

const HASH_KEY = 'neuron'
let loadStarted = false

function readHash(): string | null {
  const m = new URLSearchParams(location.hash.slice(1)).get(HASH_KEY)
  return m && /^\d{18}$/.test(m) ? m : null
}

function writeHash(rootId: string | null) {
  const url = rootId ? `#${HASH_KEY}=${rootId}` : location.pathname + location.search
  history.replaceState(null, '', url)
}

export const useStore = create<State>((set, get) => ({
  status: 'Loading metadata…',
  error: null,
  meta: null,
  attributes: null,
  overview: null,

  colorField: 'super_class',
  opacity: 0.22,
  contextBrightness: 0.18,
  focus: null,

  selection: null,
  minSyn: 5,
  showPartners: { upstream: true, downstream: true },
  showSynapses: { outgoing: false, incoming: false },

  async load() {
    // React StrictMode runs effects twice in development; load only once.
    if (loadStarted) return
    loadStarted = true
    try {
      const meta = await api.meta()
      set({ meta, status: 'Loading neuron attributes…' })
      const attributes = await api.attributes()
      set({ attributes, status: `Loading ${meta.overview.n_neurons.toLocaleString()} skeletons…` })
      const overview = await api.overview(meta.overview)
      set({ overview, status: null })
      const fromHash = readHash()
      if (fromHash) await get().select(fromHash)
      // Links pasted into an open tab only change the hash. (Our own updates use
      // replaceState, which does not fire hashchange.)
      window.addEventListener('hashchange', () => {
        const rootId = readHash()
        if (rootId !== (get().selection?.rootId ?? null)) get().select(rootId)
      })
    } catch (e) {
      get().fail(e)
    }
  },

  setColorField: (colorField) => set({ colorField, focus: null }),
  setOpacity: (opacity) => set({ opacity }),
  setContextBrightness: (contextBrightness) => set({ contextBrightness }),
  setFocus: (focus) => set({ focus }),

  async select(rootId) {
    writeHash(rootId)
    if (!rootId) {
      set({ selection: null })
      return
    }
    const attrs = get().attributes
    const index = attrs ? attrs.root_ids.indexOf(rootId) : -1
    if (index < 0) {
      get().fail(new Error(`Unknown neuron ${rootId}`))
      return
    }
    set({
      error: null,
      selection: {
        rootId,
        index,
        info: null,
        skeleton: null,
        partners: { upstream: null, downstream: null },
        synapses: { outgoing: null, incoming: null },
      },
    })
    // Only apply results that still belong to the current selection.
    const update = (patch: Partial<Selection>) => {
      const sel = get().selection
      if (sel?.rootId === rootId) set({ selection: { ...sel, ...patch } })
    }
    const { minSyn, showSynapses } = get()
    const jobs: Promise<unknown>[] = [
      api.neuron(rootId).then((info) => update({ info })),
      api.skeleton(rootId).then((skeleton) => update({ skeleton })),
      loadPartners(rootId, minSyn).then((partners) => update({ partners })),
    ]
    for (const d of ['outgoing', 'incoming'] as const) {
      if (showSynapses[d]) jobs.push(loadSynapses(rootId, d))
    }
    await Promise.all(jobs).catch(get().fail)
  },

  async setMinSyn(minSyn) {
    set({ minSyn })
    const sel = get().selection
    if (!sel) return
    try {
      const partners = await loadPartners(sel.rootId, minSyn)
      const cur = get().selection
      if (cur?.rootId === sel.rootId && get().minSyn === minSyn) {
        set({ selection: { ...cur, partners } })
      }
    } catch (e) {
      get().fail(e)
    }
  },

  togglePartners: (d) => set((s) => ({ showPartners: { ...s.showPartners, [d]: !s.showPartners[d] } })),

  toggleSynapses(d) {
    const on = !get().showSynapses[d]
    set((s) => ({ showSynapses: { ...s.showSynapses, [d]: on } }))
    const sel = get().selection
    if (on && sel && !sel.synapses[d]) loadSynapses(sel.rootId, d).catch(get().fail)
  },

  fail(e) {
    console.error(e)
    set({ error: e instanceof Error ? e.message : String(e), status: null })
  },
}))

async function loadPartners(rootId: string, minSyn: number) {
  const [upstream, downstream] = await Promise.all([
    api.partners(rootId, 'upstream', minSyn),
    api.partners(rootId, 'downstream', minSyn),
  ])
  return { upstream, downstream }
}

async function loadSynapses(rootId: string, d: SynapseDirection) {
  const data = await api.synapses(rootId, d)
  const sel = useStore.getState().selection
  if (sel?.rootId === rootId) {
    useStore.setState({ selection: { ...sel, synapses: { ...sel.synapses, [d]: data } } })
  }
}

if (import.meta.env.DEV) {
  ;(window as unknown as { store: typeof useStore }).store = useStore
}
