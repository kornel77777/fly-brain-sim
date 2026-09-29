// Typed client for the viewer API (src/fly_brain_sim/viz/api.py).
// Root IDs are strings everywhere: as JS numbers they would lose precision.

import {
  buildOverviewGeometry,
  parseSkeleton,
  parseSynapses,
  type SkeletonData,
  type SynapseData,
} from './decode'

export interface OverviewMeta {
  n_neurons: number
  n_vertices: number
  n_edges: number
  unit_nm: number
  step_nm: number
  bbox_nm: { min: [number, number, number]; max: [number, number, number] }
}

export interface Meta {
  overview: OverviewMeta
  color_fields: string[]
  has_synapses: boolean
  has_regions: boolean
}

export interface Field {
  categories: string[]
  counts: number[]
  codes: number[] // index into categories, -1 = missing
}

export interface Attributes {
  root_ids: string[]
  fields: Record<string, Field>
  representatives: number[] // one neuron per cell type and side
}

export interface RegionFlow {
  region: string
  synapses: number
}

export interface RegionStats {
  name: string // neuropil code, e.g. AL_R
  vertex_offset: number
  vertex_count: number
  index_offset: number
  index_count: number
  centroid_nm: [number, number, number]
  synapses: number
  home_neurons: number
  top_cell_types: { cell_type: string; synapses: number }[]
  flows_in: RegionFlow[]
  flows_out: RegionFlow[]
}

export interface Regions {
  regions: RegionStats[]
  vertices: Float32Array // nm
  indices: Uint32Array
}

export interface NeuronSummary {
  root_id: string
  index: number
  name: string | null
  cell_type: string | null
  super_class: string | null
  side: string | null
  nt_type: string | null
}

export interface SearchResult extends NeuronSummary {
  hemibrain_type: string | null
  matched_label: string | null
}

export interface Partner extends NeuronSummary {
  syn_count: number
}

export type Direction = 'upstream' | 'downstream'

export interface NeuronInfo {
  root_id: string
  index: number
  neuron: Record<string, string | number | null>
  annotations: Record<string, string | number | null> | null
  shiu_index: number | null
  upstream_partners: number
  downstream_partners: number
  input_synapses: number
  output_synapses: number
}

export interface SimPreset {
  id: string
  label: string
  description: string
  n_neurons: number
}

export type SimTarget =
  | { kind: 'preset'; id: string }
  | { kind: 'neurons'; root_ids: string[] }
  | { kind: 'cell_type'; cell_type: string; side?: string }
  | { kind: 'region'; region: string }

export interface SimTopNeuron {
  root_id: string
  index: number
  cell_type: string | null
  super_class: string | null
  side: string | null
  nt_type: string | null
  rate_hz: number
  first_spike_ms: number
}

export interface SimWatch {
  label: string
  n: number
  n_active: number
  rate_hz: number // mean over the group
  first_spike_ms: number | null
  indices: number[]
}

export interface SimResult {
  label: string
  watch: SimWatch[] // key neurons of a preset
  n_requested: number
  n_not_in_model: number
  sampled: boolean
  stimulated: number[] // overview indices
  rate_hz: number
  duration_ms: number
  bin_ms: number
  n_bins: number
  n_spikes: number
  kenyon_cell_share: number
  active: number[] // overview indices
  counts: number[] // active x n_bins, row-major
  top: SimTopNeuron[]
  regions: { names: string[]; counts: number[] } // region x n_bins
}

export interface Overview {
  meta: OverviewMeta
  positions: Uint16Array
  index: Uint32Array
  neuron: Float32Array
}

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`)
  return r.json() as Promise<T>
}

async function binary(url: string): Promise<ArrayBuffer> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url}: ${r.status} ${await r.text()}`)
  return r.arrayBuffer()
}

export const api = {
  meta: () => json<Meta>('/api/meta'),

  attributes: () => json<Attributes>('/api/neurons/attributes'),

  async overview(meta: OverviewMeta): Promise<Overview> {
    const [offsets, positions, parentDelta] = await Promise.all([
      binary('/api/overview/offsets.u32'),
      binary('/api/overview/positions.u16'),
      binary('/api/overview/parent_delta.u32'),
    ])
    const { index, neuron } = buildOverviewGeometry(
      new Uint32Array(offsets),
      new Uint32Array(parentDelta),
    )
    return { meta, positions: new Uint16Array(positions), index, neuron }
  },

  async regions(): Promise<Regions> {
    const [meta, vertices, indices] = await Promise.all([
      json<{ regions: RegionStats[] }>('/api/regions'),
      binary('/api/regions/vertices.f32'),
      binary('/api/regions/indices.u32'),
    ])
    return {
      regions: meta.regions,
      vertices: new Float32Array(vertices),
      indices: new Uint32Array(indices),
    }
  },

  search: (q: string, limit = 50) =>
    json<{ total: number; results: SearchResult[] }>(
      `/api/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),

  neuron: (rootId: string) => json<NeuronInfo>(`/api/neurons/${rootId}`),

  partners: (rootId: string, direction: Direction, minSyn: number) =>
    json<{ partners: Partner[] }>(
      `/api/neurons/${rootId}/partners?direction=${direction}&min_syn=${minSyn}`,
    ).then((r) => r.partners),

  simPresets: () => json<SimPreset[]>('/api/sim/presets'),

  async simulate(body: {
    target: SimTarget
    rate_hz: number
    duration_ms: number
    bin_ms?: number
  }): Promise<SimResult> {
    const r = await fetch('/api/sim/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) throw new Error(`simulation failed: ${r.status} ${await r.text()}`)
    return r.json() as Promise<SimResult>
  },

  skeleton: async (rootId: string): Promise<SkeletonData> =>
    parseSkeleton(await binary(`/api/neurons/${rootId}/skeleton`)),

  synapses: async (rootId: string, direction: 'outgoing' | 'incoming'): Promise<SynapseData> =>
    parseSynapses(await binary(`/api/neurons/${rootId}/synapses?direction=${direction}`)),
}
