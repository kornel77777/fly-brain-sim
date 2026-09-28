import { OrbitControls } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useCallback, useEffect, useMemo, useRef } from 'react'
import { Vector3, type PerspectiveCamera } from 'three'
import { DOWNSTREAM, UPSTREAM, rgbCss } from '../colors'
import { useStore } from '../store'
import { brainFrame } from './frame'
import { Overview } from './Overview'
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

function Scene() {
  const overview = useStore((s) => s.overview)
  const selection = useStore((s) => s.selection)
  const showSynapses = useStore((s) => s.showSynapses)
  const attributes = useStore((s) => s.attributes)
  const select = useStore((s) => s.select)
  const colors = useColorTable()
  const contextBrightness = useStore((s) => s.contextBrightness)
  const invalidate = useThree((s) => s.invalidate)

  // frameloop="demand": adding or removing layers doesn't redraw by itself.
  useEffect(() => {
    invalidate()
  })

  const onPick = useCallback(
    (index: number) => {
      if (attributes) select(attributes.root_ids[index])
    },
    [attributes, select],
  )

  const frame = useMemo(() => (overview ? brainFrame(overview.meta) : null), [overview])
  if (!overview || !colors || !frame) return null
  return (
    <>
      <group position={frame.position} scale={frame.scale}>
        <Overview
          data={overview}
          colorTable={colors.table}
          highlighting={colors.highlighting}
          contextBrightness={contextBrightness}
          onPick={onPick}
        />
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
