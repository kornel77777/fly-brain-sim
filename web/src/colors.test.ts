import { describe, expect, it } from 'vitest'
import {
  BOTH,
  DOWNSTREAM,
  MISSING,
  TEXTURE_WIDTH,
  UPSTREAM,
  buildColorTable,
  categoryColors,
  hexToRgb,
  partnerHighlight,
} from './colors'

describe('categoryColors', () => {
  it('uses fixed colours for neurotransmitters regardless of order', () => {
    const a = categoryColors('nt_type', ['ACH', 'GABA'])
    const b = categoryColors('nt_type', ['GABA', 'ACH'])
    expect(a[0]).toEqual(b[1])
    expect(a[1]).toEqual(b[0])
  })

  it('gives every category of a long field a colour', () => {
    const cats = Array.from({ length: 500 }, (_, i) => `t${i}`)
    const colors = categoryColors('cell_type', cats)
    expect(colors).toHaveLength(500)
    for (const c of colors) for (const v of c) expect(v).toBeGreaterThanOrEqual(0)
  })
})

describe('buildColorTable', () => {
  const colors = [hexToRgb('#ff0000'), hexToRgb('#00ff00')]

  it('pads to whole texture rows and colours by category', () => {
    const t = buildColorTable({ n: 3, codes: [0, 1, -1], colors, alpha: 1 })
    expect(t.length).toBe(TEXTURE_WIDTH * 4)
    expect(Array.from(t.slice(0, 12))).toEqual([255, 0, 0, 255, 0, 255, 0, 255, ...MISSING, 255])
  })

  it('dims everything except highlighted neurons', () => {
    const highlight = new Map([[1, [1, 2, 3, 200] as [number, number, number, number]]])
    const t = buildColorTable({ n: 3, codes: [0, 1, 0], colors, alpha: 1, highlight, othersAlpha: 0 })
    expect(t[3]).toBe(0)
    expect(Array.from(t.slice(4, 8))).toEqual([1, 2, 3, 200])
    expect(t[11]).toBe(0)
  })
})

describe('partnerHighlight', () => {
  it('colours by direction, marks reciprocal partners, and scales alpha by weight', () => {
    const h = partnerHighlight(
      [
        { index: 1, syn_count: 100 },
        { index: 2, syn_count: 1 },
      ],
      [{ index: 2, syn_count: 10 }, { index: 3, syn_count: 5 }],
    )
    expect(h.get(1)!.slice(0, 3)).toEqual(UPSTREAM)
    expect(h.get(2)!.slice(0, 3)).toEqual(BOTH)
    expect(h.get(3)!.slice(0, 3)).toEqual(DOWNSTREAM)
    expect(h.get(1)![3]).toBe(255)
    expect(h.get(3)![3]).toBeLessThan(h.get(1)![3])
  })
})
