// Turning a simulation result into colours over time.

import type { SimResult } from './api'
import type { RGB, RGBA } from './colors'

/** Bins summed to judge "firing now" (with 5 ms bins: the last 15 ms). */
export const WINDOW_BINS = 3

/** Regions below this share of the busiest region's activity are not lit. */
const MIN_REGION_LEVEL = 0.02

const HEAT: RGB[] = [
  [140, 30, 20], // just firing
  [255, 122, 26],
  [255, 242, 168], // firing hard
]
const TRACE: RGBA = [255, 122, 26, 34] // fired earlier, quiet now

export function heat(x: number): RGB {
  const t = Math.min(1, Math.max(0, x)) * (HEAT.length - 1)
  const i = Math.min(HEAT.length - 2, Math.floor(t))
  const f = t - i
  return [0, 1, 2].map((c) => Math.round(HEAT[i][c] + (HEAT[i + 1][c] - HEAT[i][c]) * f)) as RGB
}

function windowSum(counts: number[], row: number, nBins: number, bin: number): number {
  let sum = 0
  for (let b = Math.max(0, bin - WINDOW_BINS + 1); b <= bin; b++) sum += counts[row * nBins + b]
  return sum
}

/**
 * Colour per active neuron at time bin `bin`: a heat colour if it fired in the
 * last few bins (brighter for more spikes), a faint trace if it fired earlier.
 * Neurons that have not fired yet are left out.
 */
export function neuronColors(result: SimResult, bin: number): Map<number, RGBA> {
  const out = new Map<number, RGBA>()
  const { n_bins: nBins, counts, active } = result
  // spikes a neuron can fire in the window at the maximum rate (~450 Hz)
  const full = Math.max(1, (WINDOW_BINS * result.bin_ms) / 2.2)
  for (let k = 0; k < active.length; k++) {
    const now = windowSum(counts, k, nBins, bin)
    if (now > 0) {
      const x = Math.min(1, now / full)
      out.set(active[k], [...heat(x), Math.round(255 * (0.55 + 0.45 * x))])
      continue
    }
    for (let b = 0; b < bin; b++) {
      if (counts[k * nBins + b] > 0) {
        out.set(active[k], TRACE)
        break
      }
    }
  }
  return out
}

/**
 * Activity per region at `bin`, 0..1 relative to the busiest region at that
 * moment (linear, so regions with only a trickle of spikes stay dark).
 */
export function regionLevels(result: SimResult, bin: number): Map<string, number> {
  const { names, counts } = result.regions
  const nBins = result.n_bins
  const now = names.map((_, r) => windowSum(counts, r, nBins, bin))
  const max = Math.max(1, ...now)
  const out = new Map<string, number>()
  names.forEach((name, r) => {
    const level = now[r] / max
    if (level >= MIN_REGION_LEVEL) out.set(name, level)
  })
  return out
}

/** Total spikes per region over the whole run, largest first. */
export function regionTotals(result: SimResult): { region: string; spikes: number }[] {
  const { names, counts } = result.regions
  const nBins = result.n_bins
  return names
    .map((region, r) => {
      let spikes = 0
      for (let b = 0; b < nBins; b++) spikes += counts[r * nBins + b]
      return { region, spikes }
    })
    .sort((a, b) => b.spikes - a.spikes)
}

/** Number of neurons that have fired at least once by time bin `bin`. */
export function activeBy(result: SimResult, bin: number): number {
  let n = 0
  for (let k = 0; k < result.active.length; k++) {
    for (let b = 0; b <= bin; b++) {
      if (result.counts[k * result.n_bins + b] > 0) {
        n++
        break
      }
    }
  }
  return n
}
