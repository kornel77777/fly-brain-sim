import { describe, expect, it } from 'vitest'
import { buildOverviewGeometry, parseSkeleton, parseSynapses, skeletonSegments } from './decode'

describe('buildOverviewGeometry', () => {
  it('turns parent deltas into segments and tags vertices with their neuron', () => {
    // neuron 0: root, child, grandchild; neuron 1: root, two children of the root
    const offsets = new Uint32Array([0, 3, 6])
    const parentDelta = new Uint32Array([0, 1, 1, 0, 1, 2])
    const { index, neuron } = buildOverviewGeometry(offsets, parentDelta)
    expect(Array.from(index)).toEqual([0, 1, 1, 2, 3, 4, 3, 5])
    expect(Array.from(neuron)).toEqual([0, 0, 0, 1, 1, 1])
  })
})

function skeletonBuffer(xyz: number[], parent: number[], radius: number[], label: number[]) {
  const n = parent.length
  const buf = new ArrayBuffer(4 + n * 21)
  new Uint32Array(buf, 0, 1)[0] = n
  new Float32Array(buf, 4, n * 3).set(xyz)
  new Int32Array(buf, 4 + 12 * n, n).set(parent)
  new Float32Array(buf, 4 + 16 * n, n).set(radius)
  new Uint8Array(buf, 4 + 20 * n, n).set(label)
  return buf
}

describe('parseSkeleton', () => {
  it('reads the documented layout', () => {
    const buf = skeletonBuffer([0, 0, 0, 1, 0, 0, 2, 0, 0], [-1, 0, 1], [5, 1, 1], [1, 0, 6])
    const sk = parseSkeleton(buf)
    expect(sk.n).toBe(3)
    expect(Array.from(sk.parent)).toEqual([-1, 0, 1])
    expect(Array.from(sk.label)).toEqual([1, 0, 6])
    expect(Array.from(skeletonSegments(sk))).toEqual([1, 0, 0, 0, 0, 0, 2, 0, 0, 1, 0, 0])
  })

  it('rejects truncated data', () => {
    const buf = skeletonBuffer([0, 0, 0], [-1], [1], [1])
    expect(() => parseSkeleton(buf.slice(0, buf.byteLength - 1))).toThrow()
  })
})

describe('parseSynapses', () => {
  it('reads positions and partner indices', () => {
    const buf = new ArrayBuffer(4 + 2 * 16)
    new Uint32Array(buf, 0, 1)[0] = 2
    new Float32Array(buf, 4, 6).set([1, 2, 3, 4, 5, 6])
    new Uint32Array(buf, 28, 2).set([7, 139254])
    const s = parseSynapses(buf)
    expect(s.n).toBe(2)
    expect(Array.from(s.xyz)).toEqual([1, 2, 3, 4, 5, 6])
    expect(Array.from(s.partner)).toEqual([7, 139254])
  })
})
