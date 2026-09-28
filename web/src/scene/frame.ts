import type { OverviewMeta } from '../api'

// FlyWire coordinates are in nm with x -> fly's right, y -> ventral,
// z -> posterior (checked against neuropil centroids: AL_R has larger x than
// AL_L, the GNG larger y than the MB calyx, the AL smaller z than the calyx).
// That frame is left-handed, so drawing it as-is would mirror the brain.
// Flipping all three axes gives a right-handed anatomical frame in world space:
//   +x = fly's left, +y = dorsal, +z = anterior
// Scaled to micrometres and centred on the brain.
export const NM_TO_WORLD = -1e-3

export function brainFrame(meta: OverviewMeta) {
  const center = meta.bbox_nm.min.map((lo, i) => (lo + meta.bbox_nm.max[i]) / 2)
  return {
    position: center.map((c) => -c * NM_TO_WORLD) as [number, number, number],
    scale: NM_TO_WORLD,
    size: meta.bbox_nm.min.map((lo, i) => (meta.bbox_nm.max[i] - lo) / 1000) as [
      number,
      number,
      number,
    ],
  }
}
