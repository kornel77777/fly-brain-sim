// Camera presets. World frame: +x fly's left, +y dorsal, +z anterior (see frame.ts).

export type ViewName = 'front' | 'back' | 'top' | 'side'

type Vec3 = [number, number, number]

interface View {
  dir: Vec3 // from the target towards the camera
  across: 0 | 1 | 2 // world axis shown horizontally
  up: 0 | 1 | 2 // world axis shown vertically
}

export const VIEWS: Record<ViewName, View> = {
  front: { dir: [0, 0, 1], across: 0, up: 1 }, // anterior view, dorsal up
  back: { dir: [0, 0, -1], across: 0, up: 1 },
  top: { dir: [0, 1, -1e-4], across: 0, up: 2 }, // dorsal view, anterior up
  side: { dir: [-1, 0, 0], across: 2, up: 1 }, // from the fly's right, anterior to the right
}

const MARGIN = 1.08

/** Camera position that fits a box of `size` (um) for the given view. */
export function cameraPosition(
  name: ViewName,
  size: Vec3,
  fovDeg: number,
  aspect: number,
): Vec3 {
  const v = VIEWS[name]
  const t = Math.tan(((fovDeg / 2) * Math.PI) / 180)
  const depthAxis = 3 - v.across - v.up
  const dist =
    MARGIN * Math.max(size[v.up] / 2 / t, size[v.across] / 2 / (t * aspect)) + size[depthAxis] / 2
  const len = Math.hypot(...v.dir)
  return v.dir.map((d) => (d / len) * dist) as Vec3
}

/** UI -> camera: dispatch a CustomEvent<ViewName> named 'view'. */
export const viewEvents = new EventTarget()

export function showView(name: ViewName) {
  viewEvents.dispatchEvent(new CustomEvent('view', { detail: name }))
}
