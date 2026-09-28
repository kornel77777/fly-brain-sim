import { useThree } from '@react-three/fiber'
import { useEffect, useMemo } from 'react'
import { DoubleSide } from 'three'
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js'
import { LineSegments2 } from 'three/examples/jsm/lines/LineSegments2.js'
import { LineSegmentsGeometry } from 'three/examples/jsm/lines/LineSegmentsGeometry.js'
import { skeletonSegments, type SkeletonData } from '../decode'

const COLOR = '#ffffff'
const MIN_SOMA_RADIUS_NM = 1500

/** Full-resolution skeleton of the selected neuron, in nm (inside the brain frame). */
export function SelectedNeuron({ skeleton }: { skeleton: SkeletonData }) {
  const size = useThree((s) => s.size)

  const line = useMemo(() => {
    const geometry = new LineSegmentsGeometry()
    geometry.setPositions(skeletonSegments(skeleton))
    const material = new LineMaterial({ color: COLOR, linewidth: 2, worldUnits: false })
    // Drawn after (and over) the transparent overview.
    material.transparent = true
    material.depthTest = false
    // The quads are built in screen space, so the brain frame's mirroring does not
    // really flip them, but three.js flips face culling for mirrored meshes.
    material.side = DoubleSide
    const l = new LineSegments2(geometry, material)
    l.frustumCulled = false
    l.renderOrder = 10
    return l
  }, [skeleton])

  useEffect(() => {
    ;(line.material as LineMaterial).resolution.set(size.width, size.height)
  }, [line, size])

  useEffect(
    () => () => {
      line.geometry.dispose()
      ;(line.material as LineMaterial).dispose()
    },
    [line],
  )

  const soma = useMemo(() => {
    let i = skeleton.label.indexOf(1)
    if (i < 0) i = skeleton.parent.indexOf(-1)
    const p = skeleton.xyz.subarray(i * 3, i * 3 + 3)
    return {
      position: [p[0], p[1], p[2]] as [number, number, number],
      radius: Math.max(skeleton.radius[i], MIN_SOMA_RADIUS_NM),
    }
  }, [skeleton])

  return (
    <>
      <primitive object={line} />
      <mesh position={soma.position} renderOrder={10}>
        <sphereGeometry args={[soma.radius, 24, 16]} />
        <meshBasicMaterial color={COLOR} transparent depthTest={false} />
      </mesh>
    </>
  )
}
