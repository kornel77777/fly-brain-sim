import type { Ray } from 'three'

// Scene layers register how to pick themselves; the canvas-level handler asks
// them in order (neurons first, then regions).

type NeuronPicker = (x: number, y: number) => number | null // css px in the canvas
type RegionPicker = (worldRay: Ray) => string | null

export const pickers: { neuron: NeuronPicker | null; region: RegionPicker | null } = {
  neuron: null,
  region: null,
}
