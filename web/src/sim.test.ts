import { describe, expect, it } from 'vitest'
import type { SimResult } from './api'
import { activeBy, heat, neuronColors, regionLevels, regionTotals } from './sim'

function result(counts: number[][], regions: Record<string, number[]> = {}): SimResult {
  const names = Object.keys(regions)
  return {
    label: 'test',
    watch: [],
    n_requested: 1,
    n_not_in_model: 0,
    sampled: false,
    stimulated: [10],
    rate_hz: 150,
    duration_ms: counts[0].length * 5,
    bin_ms: 5,
    n_bins: counts[0].length,
    n_spikes: counts.flat().reduce((a, b) => a + b, 0),
    kenyon_cell_share: 0,
    active: counts.map((_, i) => 10 + i),
    counts: counts.flat(),
    top: [],
    regions: { names, counts: names.flatMap((n) => regions[n]) },
  }
}

describe('heat', () => {
  it('runs from dark red to pale yellow and clamps', () => {
    expect(heat(0)).toEqual([140, 30, 20])
    expect(heat(1)).toEqual([255, 242, 168])
    expect(heat(5)).toEqual(heat(1))
  })
})

describe('neuronColors', () => {
  // neuron 10 fires early, neuron 11 fires late, neuron 12 fires throughout
  const r = result([
    [1, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 2],
    [2, 2, 2, 2, 2, 2],
  ])

  it('shows neurons firing now, traces earlier firing, and hides what has not fired yet', () => {
    const at0 = neuronColors(r, 0)
    expect(at0.has(10) && at0.has(12) && !at0.has(11)).toBe(true)
    const at5 = neuronColors(r, 5)
    expect(at5.get(10)![3]).toBeLessThan(60) // faint trace
    expect(at5.get(11)![3]).toBeGreaterThan(100) // firing now
  })
})

describe('region summaries', () => {
  const r = result([[1, 1, 1, 1, 1]], {
    GNG: [5, 0, 0, 0, 0],
    PRW: [0, 0, 2, 0, 0],
    LO_R: [0, 0, 0, 0, 1000],
  })

  it('scales region levels to the busiest region at that moment', () => {
    // bin 2 window covers bins 0-2: GNG 5, PRW 2
    const at2 = regionLevels(r, 2)
    expect(at2.get('GNG')).toBeCloseTo(1)
    expect(at2.get('PRW')).toBeCloseTo(0.4)
    expect(at2.has('LO_R')).toBe(false)
  })

  it('leaves regions with only a trickle of activity dark', () => {
    const quiet = result([[0, 0, 0, 0, 1]], { A: [0, 0, 0, 0, 1000], B: [0, 0, 0, 0, 5] })
    const at4 = regionLevels(quiet, 4)
    expect(at4.get('A')).toBeCloseTo(1)
    expect(at4.has('B')).toBe(false)
  })

  it('totals regions and counts neurons active so far', () => {
    expect(regionTotals(r)).toEqual([
      { region: 'LO_R', spikes: 1000 },
      { region: 'GNG', spikes: 5 },
      { region: 'PRW', spikes: 2 },
    ])
    expect(activeBy(r, 0)).toBe(1)
  })
})
