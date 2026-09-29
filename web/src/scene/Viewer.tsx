import { OrbitControls } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import { Raycaster, Vector2, Vector3, type PerspectiveCamera } from 'three'
import { DOWNSTREAM, UPSTREAM, rgbCss } from '../colors'
import { useStore } from '../store'
import { brainFrame } from './frame'
import { Overview } from './Overview'
import { pickers } from './picking'
import { Regions } from './Regions'
import { SelectedNeuron } from './SelectedNeuron'
import { Synapses } from './Synapses'
import { useColorTable } from './useColorTable'
import { cameraPosition, showView, viewEvents, type ViewName } from './views'

type Size = [number, number, number]

function CameraRig({ size }: { size: Size }) {
  const camera = useThree((s) => s.camera) as PerspectiveCamera
  const aspect = useThree((s) => s.size.width / s.size.height)
  const invalidate = useThree((s) => s.invalidate)
  const controls = useThree((s) => s.controls) as unknown as {
    target: Vector3
    update: () => void
  } | null

  useEffect(() => {
    const onView = (e: Event) => {
      const name = (e as CustomEvent<ViewName>).detail
      camera.position.set(...cameraPosition(name, size, camera.fov, aspect))
      controls?.target.set(0, 0, 0)
      controls?.update()
      invalidate()
    }
    viewEvents.addEventListener('view', onView)
    return () => viewEvents.removeEventListener('view', onView)
  }, [camera, controls, size, aspect, invalidate])

  // Fit the brain once, when it first appears.
  const fitted = useRef(false)
  useEffect(() => {
    if (fitted.current || !controls) return
    fitted.current = true
    showView('front')
  }, [controls])
  return null
}

/** Anatomical direction labels, projected every frame (plain DOM, no portals). */
function OrientationLabels({ size }: { size: Size }) {
  const camera = useThree((s) => s.camera)
  const gl = useThree((s) => s.gl)
  const refs = useRef<(HTMLSpanElement | null)[]>([])
  const labels = useMemo((): [string, string, Vector3][] => {
    const [x, y] = [size[0] / 2 + 30, size[1] / 2 + 30]
    return [
      ['D', 'dorsal', new Vector3(0, y, 0)],
      ['V', 'ventral', new Vector3(0, -y, 0)],
      ['L', "fly's left", new Vector3(x, 0, 0)],
      ['R', "fly's right", new Vector3(-x, 0, 0)],
    ]
  }, [size])

  useEffect(() => {
    const parent = gl.domElement.parentElement
    if (!parent) return
    const container = document.createElement('div')
    container.className = 'axis-labels'
    for (const [i, [text, title]] of labels.entries()) {
      const span = document.createElement('span')
      span.className = 'axis-label'
      span.textContent = text
      span.title = title
      refs.current[i] = span
      container.appendChild(span)
    }
    parent.appendChild(container)
    return () => container.remove()
  }, [gl, labels])

  const v = useMemo(() => new Vector3(), [])
  useFrame(() => {
    const { width, height } = gl.domElement.getBoundingClientRect()
    labels.forEach(([, , pos], i) => {
      const el = refs.current[i]
      if (!el) return
      v.copy(pos).project(camera)
      const visible = v.z < 1 && Math.abs(v.x) < 1.05 && Math.abs(v.y) < 1.05
      el.style.display = visible ? '' : 'none'
      const px = ((v.x + 1) / 2) * width
      const py = ((1 - v.y) / 2) * height
      el.style.transform = `translate(${px}px, ${py}px) translate(-50%, -50%)`
    })
  })
  return null
}

const CLICK_SLOP = 4 // px of pointer movement still treated as a click
const HOVER_MS = 60

/** Click: pick a neuron, else a region. Hover: name the region under the pointer. */
function CanvasInput() {
  const gl = useThree((s) => s.gl)
  const camera = useThree((s) => s.camera)
  const attributes = useStore((s) => s.attributes)
  const select = useStore((s) => s.select)
  const selectRegion = useStore((s) => s.selectRegion)
  const setHover = useStore((s) => s.setHover)

  useEffect(() => {
    const el = gl.domElement
    const raycaster = new Raycaster()
    const ndc = new Vector2()
    const regionAt = (x: number, y: number, rect: DOMRect) => {
      if (!pickers.region) return null
      ndc.set((x / rect.width) * 2 - 1, -(y / rect.height) * 2 + 1)
      raycaster.setFromCamera(ndc, camera)
      return pickers.region(raycaster.ray)
    }

    let down: { x: number; y: number } | null = null
    let lastHover = 0
    const onDown = (e: PointerEvent) => {
      down = { x: e.clientX, y: e.clientY }
    }
    const onUp = (e: PointerEvent) => {
      if (!down || e.button !== 0) return
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y)
      down = null
      if (moved > CLICK_SLOP) return
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const neuron = pickers.neuron?.(x, y) ?? null
      if (neuron !== null && attributes) {
        select(attributes.root_ids[neuron])
        return
      }
      const region = regionAt(x, y, rect)
      if (region) selectRegion(region)
    }
    const onMove = (e: PointerEvent) => {
      if (e.buttons !== 0) return
      const now = performance.now()
      if (now - lastHover < HOVER_MS) return
      lastHover = now
      const rect = el.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const region = regionAt(x, y, rect)
      setHover(region ? { region, x, y } : null)
    }
    const onLeave = () => setHover(null)
    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointerup', onUp)
    el.addEventListener('pointermove', onMove)
    el.addEventListener('pointerleave', onLeave)
    return () => {
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointerup', onUp)
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerleave', onLeave)
    }
  }, [gl, camera, attributes, select, selectRegion, setHover])
  return null
}

const REGION_OPACITY = { regions: 0.9, sketch: 0.55, all: 0.3 }

/** Per-region emphasis: 1 normal, higher for hovered/selected, lower for the rest. */
function useRegionEmphasis(): Float32Array | null {
  const regions = useStore((s) => s.regions)
  const region = useStore((s) => s.region)
  const hover = useStore((s) => s.hover?.region ?? null)
  const neuronSelected = useStore((s) => s.selection !== null)
  return useMemo(() => {
    if (!regions) return null
    return Float32Array.from(regions.regions, (r) => {
      if (r.name === region) return 3
      if (r.name === hover) return 2
      if (region) return 0.45
      return neuronSelected ? 0.6 : 1
    })
  }, [regions, region, hover, neuronSelected])
}

function Scene() {
  const overview = useStore((s) => s.overview)
  const selection = useStore((s) => s.selection)
  const showSynapses = useStore((s) => s.showSynapses)
  const colors = useColorTable()
  const contextBrightness = useStore((s) => s.contextBrightness)
  const regions = useStore((s) => s.regions)
  const detail = useStore((s) => s.detail)
  const emphasis = useRegionEmphasis()
  const invalidate = useThree((s) => s.invalidate)

  // frameloop="demand": adding or removing layers doesn't redraw by itself.
  useEffect(() => {
    invalidate()
  })

  const meta = useStore((s) => s.meta)
  const frame = useMemo(() => (meta ? brainFrame(meta.overview) : null), [meta])
  if (!frame) return null
  return (
    <>
      <group position={frame.position} scale={frame.scale}>
        {regions && emphasis && (
          <Regions data={regions} emphasis={emphasis} opacity={REGION_OPACITY[detail]} />
        )}
        {overview && colors && (
          <Overview
            data={overview}
            colorTable={colors.table}
            highlighting={colors.highlighting}
            contextBrightness={contextBrightness}
          />
        )}
        {selection?.skeleton && <SelectedNeuron skeleton={selection.skeleton} />}
        {showSynapses.outgoing && selection?.synapses.outgoing && (
          <Synapses data={selection.synapses.outgoing} color={rgbCss(DOWNSTREAM)} />
        )}
        {showSynapses.incoming && selection?.synapses.incoming && (
          <Synapses data={selection.synapses.incoming} color={rgbCss(UPSTREAM)} />
        )}
      </group>
      <OrientationLabels size={frame.size} />
      <CameraRig size={frame.size} />
      <CanvasInput />
    </>
  )
}

export function Viewer() {
  return (
    <Canvas
      camera={{ fov: 35, near: 1, far: 20000, position: [0, 0, 1500] }}
      frameloop="demand"
      dpr={[1, 2]}
      gl={{ antialias: true }}
    >
      <color attach="background" args={['#04050a']} />
      <OrbitControls makeDefault enableDamping dampingFactor={0.15} />
      <Scene />
    </Canvas>
  )
}
