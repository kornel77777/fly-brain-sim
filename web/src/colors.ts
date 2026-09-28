// Per-neuron colour table: RGBA8 per neuron, uploaded as a texture the
// overview shader looks up by neuron index. Alpha 0 hides a neuron.

export type RGB = [number, number, number]
export type RGBA = [number, number, number, number]

export const TEXTURE_WIDTH = 1024

const PALETTE: string[] = [
  '#5ab4ff', '#ff9f40', '#5fd38d', '#ff6b6b', '#b18cff', '#ffd54f', '#4dd0e1',
  '#f06292', '#aed581', '#ff8a65', '#7986cb', '#e0c19e', '#4db6ac', '#ba68c8',
  '#fff176', '#90a4ae', '#dce775', '#9575cd', '#81c784', '#e57373',
]

// Colours with a fixed meaning, so they stay stable across views.
const FIXED: Record<string, Record<string, string>> = {
  nt_type: {
    ACH: '#ff9f40',
    GABA: '#5ab4ff',
    GLUT: '#b18cff',
    DA: '#ffd54f',
    SER: '#4dd0e1',
    OCT: '#f06292',
  },
  side: { left: '#ff6b6b', right: '#5ab4ff', center: '#ffd54f' },
  flow: { intrinsic: '#90a4ae', afferent: '#5fd38d', efferent: '#ff6b6b' },
}

export const MISSING: RGB = [85, 85, 85]
export const UPSTREAM: RGB = [77, 208, 225] // cyan: inputs to the selected neuron
export const DOWNSTREAM: RGB = [255, 159, 64] // orange: its outputs
export const BOTH: RGB = [240, 98, 146]

export function hexToRgb(hex: string): RGB {
  const v = parseInt(hex.slice(1), 16)
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255]
}

function hslToRgb(h: number, s: number, l: number): RGB {
  const a = s * Math.min(l, 1 - l)
  const f = (n: number) => {
    const k = (n + h / 30) % 12
    return Math.round(255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))))
  }
  return [f(0), f(8), f(4)]
}

/** Colour for each category (categories are sorted by frequency). */
export function categoryColors(field: string, categories: string[]): RGB[] {
  const fixed = FIXED[field] ?? {}
  return categories.map((c, i) => {
    if (fixed[c]) return hexToRgb(fixed[c])
    if (i < PALETTE.length) return hexToRgb(PALETTE[i])
    // Long tail (e.g. 8,000+ cell types): spread hues with the golden angle.
    return hslToRgb((i * 137.508) % 360, 0.65, 0.6)
  })
}

export interface ColorTableOptions {
  n: number
  codes: ArrayLike<number> | null // category per neuron, -1 = missing
  colors: RGB[]
  alpha: number // 0..1 for neurons in the normal state
  highlight?: Map<number, RGBA> | null // non-null = highlight mode; index -> colour override
  othersAlpha?: number // alpha for everything else while highlighting
}

export function textureRows(n: number): number {
  return Math.max(1, Math.ceil(n / TEXTURE_WIDTH))
}

export function buildColorTable(o: ColorTableOptions, out?: Uint8Array): Uint8Array {
  const size = TEXTURE_WIDTH * textureRows(o.n) * 4
  const table = out && out.length === size ? out : new Uint8Array(size)
  const highlighting = o.highlight != null
  const a = Math.round(255 * (highlighting ? (o.othersAlpha ?? 0) : o.alpha))
  for (let i = 0; i < o.n; i++) {
    const code = o.codes ? o.codes[i] : -1
    const c = code >= 0 ? o.colors[code] : MISSING
    const k = i * 4
    table[k] = c[0]
    table[k + 1] = c[1]
    table[k + 2] = c[2]
    table[k + 3] = a
  }
  if (highlighting) {
    for (const [i, c] of o.highlight!) {
      const k = i * 4
      table[k] = c[0]
      table[k + 1] = c[1]
      table[k + 2] = c[2]
      table[k + 3] = c[3]
    }
  }
  return table
}

/** Partner highlight: direction colour, brighter for stronger connections. */
export function partnerHighlight(
  upstream: { index: number; syn_count: number }[],
  downstream: { index: number; syn_count: number }[],
): Map<number, RGBA> {
  const max = Math.max(1, ...upstream.map((p) => p.syn_count), ...downstream.map((p) => p.syn_count))
  const alpha = (syn: number) => Math.round(255 * (0.35 + 0.65 * (Math.log1p(syn) / Math.log1p(max))))
  const out = new Map<number, RGBA>()
  const up = new Map(upstream.map((p) => [p.index, p.syn_count]))
  for (const p of upstream) out.set(p.index, [...UPSTREAM, alpha(p.syn_count)])
  for (const p of downstream) {
    const both = up.has(p.index)
    const syn = both ? Math.max(p.syn_count, up.get(p.index)!) : p.syn_count
    out.set(p.index, [...(both ? BOTH : DOWNSTREAM), alpha(syn)])
  }
  return out
}

export function rgbCss(c: RGB): string {
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`
}
