import { useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { Regions as RegionsData } from '../api'
import { hexToRgb } from '../colors'
import { regionInfo } from '../content'
import { pickers } from './picking'

const TEX_WIDTH = 128 // >= number of regions (78)

// Rim shading: faces seen head-on are nearly transparent, edges glow, so each
// region reads as a soft outline instead of a solid blob. Per-region colour and
// emphasis come from a small texture indexed by the vertex's region.
const vertexShader = /* glsl */ `
  in float region;
  uniform highp sampler2D regionColors;
  out vec4 vColor;
  out vec3 vNormal;
  out vec3 vView;

  void main() {
    vColor = texelFetch(regionColors, ivec2(int(region + 0.5), 0), 0);
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`

const fragmentShader = /* glsl */ `
  in vec4 vColor;
  in vec3 vNormal;
  in vec3 vView;
  uniform float uOpacity;
  layout(location = 0) out highp vec4 fragColor;

  void main() {
    float emphasis = vColor.a * 4.0; // texture stores emphasis / 4
    if (emphasis <= 0.0) discard;
    float facing = abs(dot(normalize(vNormal), normalize(vView)));
    float rim = pow(1.0 - facing, 2.0);
    float alpha = clamp(uOpacity * emphasis * (0.15 + 0.85 * rim), 0.0, 1.0);
    fragColor = vec4(vColor.rgb * (0.55 + 0.65 * rim), alpha);
  }
`

interface Props {
  data: RegionsData
  emphasis: Float32Array // per region, 0 hides, 1 normal, >1 stronger (max 4)
  opacity: number
}

export function Regions({ data, emphasis, opacity }: Props) {
  const invalidate = useThree((s) => s.invalidate)
  const meshRef = useRef<THREE.Mesh>(null)

  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(data.vertices, 3))
    const region = new Float32Array(data.vertices.length / 3)
    data.regions.forEach((r, i) =>
      region.fill(i, r.vertex_offset, r.vertex_offset + r.vertex_count),
    )
    g.setAttribute('region', new THREE.BufferAttribute(region, 1))
    g.setIndex(new THREE.BufferAttribute(data.indices, 1))
    g.computeVertexNormals()
    return g
  }, [data])

  const texture = useMemo(() => {
    const t = new THREE.DataTexture(
      new Uint8Array(TEX_WIDTH * 4),
      TEX_WIDTH,
      1,
      THREE.RGBAFormat,
      THREE.UnsignedByteType,
    )
    t.minFilter = t.magFilter = THREE.NearestFilter
    return t
  }, [])

  useEffect(() => {
    uploadRegionColors(texture, data, emphasis)
    invalidate()
  }, [texture, data, emphasis, invalidate])

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        glslVersion: THREE.GLSL3,
        vertexShader,
        fragmentShader,
        uniforms: { regionColors: { value: texture }, uOpacity: { value: 0 } },
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    [texture],
  )

  useEffect(() => {
    setOpacity(material, opacity)
    invalidate()
  }, [material, opacity, invalidate])

  // Ray picking: test each region's bounding box, then its triangles.
  const boxes = useMemo(
    () =>
      data.regions.map((r) => {
        const box = new THREE.Box3()
        const v = data.vertices
        for (let i = r.vertex_offset; i < r.vertex_offset + r.vertex_count; i++) {
          box.expandByPoint(new THREE.Vector3(v[i * 3], v[i * 3 + 1], v[i * 3 + 2]))
        }
        return box
      }),
    [data],
  )

  useEffect(() => {
    const a = new THREE.Vector3()
    const b = new THREE.Vector3()
    const c = new THREE.Vector3()
    const hit = new THREE.Vector3()
    const inverse = new THREE.Matrix4()
    pickers.region = (worldRay) => {
      const mesh = meshRef.current
      if (!mesh) return null
      mesh.updateWorldMatrix(true, false)
      const ray = worldRay.clone().applyMatrix4(inverse.copy(mesh.matrixWorld).invert())
      const v = data.vertices
      const idx = data.indices
      let best: string | null = null
      let bestDist = Infinity
      data.regions.forEach((r, ri) => {
        if (emphasis[ri] <= 0 || !ray.intersectsBox(boxes[ri])) return
        for (let k = r.index_offset; k < r.index_offset + r.index_count; k += 3) {
          a.fromArray(v, idx[k] * 3)
          b.fromArray(v, idx[k + 1] * 3)
          c.fromArray(v, idx[k + 2] * 3)
          if (ray.intersectTriangle(a, b, c, false, hit)) {
            const d = hit.distanceTo(ray.origin)
            if (d < bestDist) {
              bestDist = d
              best = r.name
            }
          }
        }
      })
      return best
    }
    return () => {
      pickers.region = null
    }
  }, [data, boxes, emphasis])

  useEffect(
    () => () => {
      geometry.dispose()
      texture.dispose()
      material.dispose()
    },
    [geometry, texture, material],
  )

  return (
    <mesh
      ref={meshRef}
      geometry={geometry}
      material={material}
      frustumCulled={false}
      renderOrder={2}
    />
  )
}

function setOpacity(material: THREE.ShaderMaterial, value: number) {
  material.uniforms.uOpacity.value = value
}

function uploadRegionColors(texture: THREE.DataTexture, data: RegionsData, emphasis: Float32Array) {
  const px = texture.image.data as Uint8Array
  data.regions.forEach((r, i) => {
    const [cr, cg, cb] = hexToRgb(regionInfo(r.name).group.color)
    px.set([cr, cg, cb, Math.round(255 * Math.min(1, Math.max(0, emphasis[i] / 4)))], i * 4)
  })
  texture.needsUpdate = true
}
