// Decoders for the API's binary responses. All little-endian (the browser's
// native byte order on every platform we target).

/** Line-segment index pairs and per-vertex neuron index for the overview. */
export function buildOverviewGeometry(
  offsets: Uint32Array,
  parentDelta: Uint32Array,
): { index: Uint32Array; neuron: Float32Array } {
  const nVertices = parentDelta.length
  const neuron = new Float32Array(nVertices)
  for (let i = 0; i + 1 < offsets.length; i++) {
    neuron.fill(i, offsets[i], offsets[i + 1])
  }
  let nEdges = 0
  for (let v = 0; v < nVertices; v++) if (parentDelta[v] > 0) nEdges++
  const index = new Uint32Array(nEdges * 2)
  let k = 0
  for (let v = 0; v < nVertices; v++) {
    const d = parentDelta[v]
    if (d > 0) {
      index[k++] = v - d
      index[k++] = v
    }
  }
  return { index, neuron }
}

export interface SkeletonData {
  n: number
  xyz: Float32Array // n * 3, nm
  parent: Int32Array // -1 = root
  radius: Float32Array // nm
  label: Uint8Array // SWC label, 1 = soma
}

/** Layout: n (u32), xyz (f32 n*3), parent (i32 n), radius (f32 n), label (u8 n). */
export function parseSkeleton(buf: ArrayBuffer): SkeletonData {
  const n = new Uint32Array(buf, 0, 1)[0]
  let o = 4
  const xyz = new Float32Array(buf, o, n * 3)
  o += 12 * n
  const parent = new Int32Array(buf, o, n)
  o += 4 * n
  const radius = new Float32Array(buf, o, n)
  o += 4 * n
  const label = new Uint8Array(buf, o, n)
  if (o + n !== buf.byteLength) throw new Error('unexpected skeleton size')
  return { n, xyz, parent, radius, label }
}

/** Endpoints of every (node, parent) edge, 6 floats per segment. */
export function skeletonSegments(sk: SkeletonData): Float32Array {
  let nEdges = 0
  for (let i = 0; i < sk.n; i++) if (sk.parent[i] >= 0) nEdges++
  const out = new Float32Array(nEdges * 6)
  let k = 0
  for (let i = 0; i < sk.n; i++) {
    const p = sk.parent[i]
    if (p < 0) continue
    out.set(sk.xyz.subarray(i * 3, i * 3 + 3), k)
    out.set(sk.xyz.subarray(p * 3, p * 3 + 3), k + 3)
    k += 6
  }
  return out
}

export interface SynapseData {
  n: number
  xyz: Float32Array // n * 3, nm (cleft centres)
  partner: Uint32Array // overview index of the other neuron
}

/** Layout: n (u32), xyz (f32 n*3), partner index (u32 n). */
export function parseSynapses(buf: ArrayBuffer): SynapseData {
  const n = new Uint32Array(buf, 0, 1)[0]
  const xyz = new Float32Array(buf, 4, n * 3)
  const partner = new Uint32Array(buf, 4 + 12 * n, n)
  if (4 + 16 * n !== buf.byteLength) throw new Error('unexpected synapse size')
  return { n, xyz, partner }
}
