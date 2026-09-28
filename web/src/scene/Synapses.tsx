import { useEffect, useMemo } from 'react'
import * as THREE from 'three'
import type { SynapseData } from '../decode'

/** Synapse cleft centres as screen-sized dots (positions in nm, inside the brain frame). */
export function Synapses({ data, color }: { data: SynapseData; color: string }) {
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(data.xyz, 3))
    return g
  }, [data])

  useEffect(() => () => geometry.dispose(), [geometry])

  return (
    <points geometry={geometry} frustumCulled={false} renderOrder={11}>
      <pointsMaterial
        color={color}
        size={4}
        sizeAttenuation={false}
        transparent
        opacity={0.9}
        depthWrite={false}
        depthTest={false}
      />
    </points>
  )
}
