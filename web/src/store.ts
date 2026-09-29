import { create } from 'zustand'
import {
  api,
  type Attributes,
  type Direction,
  type Meta,
  type NeuronInfo,
  type Overview,
  type Partner,
  type Regions,
  type SimPreset,
  type SimResult,
  type SimTarget,
} from './api'
import type { SkeletonData, SynapseData } from './decode'

export type Focus =
  | { kind: 'category'; field: string; code: number; label: string }
  | { kind: 'set'; label: string; indices: number[] }

export type SynapseDirection = 'outgoing' | 'incoming'

/** How much of the brain to draw: regions only, one neuron per cell type, or everything. */
export type Detail = 'regions' | 'sketch' | 'all'

export type Tab = 'explore' | 'regions' | 'stimulate'

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
  regions: Regions | null

  tab: Tab
  detail: Detail
  region: string | null // selected region (neuropil code)
  hover: { region: string; x: number; y: number } | null // region under the pointer
  colorField: string
  opacity: number
  contextBrightness: number // 0..1 brightness of neurons outside a highlight; 0 hides them
  focus: Focus | null

  sim: {
    presets: SimPreset[] | null
    target: SimTarget | null
    targetLabel: string | null
    rateHz: number
    durationMs: number
    running: boolean
    result: SimResult | null
    bin: number // current playback position, in time bins (fractional)
    playing: boolean
  }

  selection: Selection | null
  minSyn: number
  showPartners: Record<Direction, boolean>
  showSynapses: Record<SynapseDirection, boolean>

  load: () => Promise<void>
  setTab: (t: Tab) => void
  setDetail: (d: Detail) => void
  selectRegion: (code: string | null) => void
  setHover: (h: State['hover']) => void
  setColorField: (field: string) => void
  setOpacity: (v: number) => void
  setContextBrightness: (v: number) => void
  setFocus: (f: Focus | null) => void
  select: (rootId: string | null) => Promise<void>
  setMinSyn: (v: number) => void
  togglePartners: (d: Direction) => void
  toggleSynapses: (d: SynapseDirection) => void
  fail: (e: unknown) => void

  loadSimPresets: () => Promise<void>
  setSimTarget: (target: SimTarget, label: string) => void
  setSim: (patch: Partial<Pick<State['sim'], 'rateHz' | 'durationMs' | 'bin' | 'playing'>>) => void
  runSim: () => Promise<void>
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
  regions: null,

  tab: 'explore',
  detail: 'sketch',
  region: null,
  hover: null,
  colorField: 'super_class',
  opacity: 0.3,
  contextBrightness: 0.18,
  focus: null,

  sim: {
    presets: null,
    target: null,
    targetLabel: null,
    rateHz: 150,
    durationMs: 300,
    running: false,
    result: null,
    bin: 0,
    playing: false,
  },

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
      // Regions are small; start them first so the brain's outline appears early.
      const regions = meta.has_regions ? api.regions() : Promise.resolve(null)
      regions.then((r) => set({ regions: r })).catch(get().fail)
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

  setTab: (tab) => set({ tab }),
  setDetail: (detail) => set({ detail }),
  setHover: (hover) => set({ hover }),

  selectRegion(region) {
    if (region) {
      writeHash(null)
      set({ region, selection: null, focus: null, tab: 'explore' })
    } else {
      set({ region: null })
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
    set({ region: null, tab: 'explore' })
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

  async loadSimPresets() {
    if (get().sim.presets) return
    try {
      const presets = await api.simPresets()
      set((s) => ({ sim: { ...s.sim, presets } }))
    } catch (e) {
      get().fail(e)
    }
  },

  setSimTarget: (target, targetLabel) =>
    set((s) => ({ sim: { ...s.sim, target, targetLabel }, tab: 'stimulate' })),

  setSim: (patch) => set((s) => ({ sim: { ...s.sim, ...patch } })),

  async runSim() {
    const { sim } = get()
    if (!sim.target || sim.running) return
    set({ sim: { ...sim, running: true, playing: false }, error: null })
    try {
      const result = await api.simulate({
        target: sim.target,
        rate_hz: sim.rateHz,
        duration_ms: sim.durationMs,
      })
      set((s) => ({ sim: { ...s.sim, running: false, result, bin: 0, playing: true } }))
    } catch (e) {
      set((s) => ({ sim: { ...s.sim, running: false } }))
      get().fail(e)
    }
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
