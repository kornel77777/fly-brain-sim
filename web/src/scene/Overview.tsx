import { useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { Overview as OverviewData } from '../api'
import { TEXTURE_WIDTH, textureRows } from '../colors'

// The colour table's alpha decides which pass draws a neuron:
//   alpha > 0   main pass, normal alpha blending (the usual view, or highlighted neurons)
//   alpha == 0  context pass, drawn only while something is highlighted: MAX blending
//               of the colour scaled by uBrightness, i.e. a dim maximum-intensity
//               projection that stays dim however many lines overlap.
const vertexShader = /* glsl */ `
  in float neuron;
  uniform highp sampler2D colors;
  out vec4 vColor;
  const int W = ${TEXTURE_WIDTH};

  void main() {
    int i = int(neuron + 0.5);
    vColor = texelFetch(colors, ivec2(i % W, i / W), 0);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const mainFragmentShader = /* glsl */ `
  in vec4 vColor;
  layout(location = 0) out highp vec4 fragColor;
  void main() {
    if (vColor.a == 0.0) discard;
    fragColor = vColor;
  }
`

const contextFragmentShader = /* glsl */ `
  in vec4 vColor;
  uniform float uBrightness;
  layout(location = 0) out highp vec4 fragColor;
  void main() {
    if (vColor.a > 0.0) discard;
    fragColor = vec4(vColor.rgb * uBrightness, 1.0);
  }
`

// Picking: encode (neuron index + 1) in RGB. Context neurons are pickable
// only while they are visible.
const pickVertexShader = /* glsl */ `
  in float neuron;
  uniform highp sampler2D colors;
  uniform float uPickContext;
  out vec4 vId;
  const int W = ${TEXTURE_WIDTH};

  void main() {
    int i = int(neuron + 0.5);
    float alpha = texelFetch(colors, ivec2(i % W, i / W), 0).a;
    float visible = alpha > 0.0 ? 1.0 : uPickContext;
    int id = i + 1;
    vId = vec4(float(id & 255) / 255.0, float((id >> 8) & 255) / 255.0,
               float((id >> 16) & 255) / 255.0, visible);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const pickFragmentShader = /* glsl */ `
  in vec4 vId;
  layout(location = 0) out highp vec4 fragColor;
  void main() {
    if (vId.a < 0.5) discard;
    fragColor = vec4(vId.rgb, 1.0);
  }
`

const PICK_RADIUS = 6 // px around the cursor; lines are 1 px wide
const CLICK_SLOP = 4 // px of pointer movement still treated as a click

function setUniform(material: THREE.ShaderMaterial, name: string, value: number) {
  material.uniforms[name].value = value
}

function uploadColors(texture: THREE.DataTexture, table: Uint8Array) {
  ;(texture.image.data as Uint8Array).set(table)
  texture.needsUpdate = true
}

interface Props {
  data: OverviewData
  colorTable: Uint8Array
  highlighting: boolean // whether the context pass is needed
  contextBrightness: number // 0 hides non-highlighted neurons
  onPick: (index: number) => void
}

export function Overview({ data, colorTable, highlighting, contextBrightness, onPick }: Props) {
  const { gl, camera, size, invalidate } = useThree()
  const meshRef = useRef<THREE.LineSegments>(null)

  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(data.positions, 3))
    g.setAttribute('neuron', new THREE.BufferAttribute(data.neuron, 1))
    g.setIndex(new THREE.BufferAttribute(data.index, 1))
    return g
  }, [data])

  const texture = useMemo(() => {
    const rows = textureRows(data.meta.n_neurons)
    const t = new THREE.DataTexture(
      new Uint8Array(TEXTURE_WIDTH * rows * 4),
      TEXTURE_WIDTH,
      rows,
      THREE.RGBAFormat,
      THREE.UnsignedByteType,
    )
    t.minFilter = t.magFilter = THREE.NearestFilter
    return t
  }, [data])

  useEffect(() => {
    uploadColors(texture, colorTable)
    invalidate()
  }, [texture, colorTable, invalidate])

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        glslVersion: THREE.GLSL3,
        vertexShader,
        fragmentShader: mainFragmentShader,
        uniforms: { colors: { value: texture } },
        transparent: true,
        depthWrite: false,
      }),
    [texture],
  )

  const contextMaterial = useMemo(
    () =>
      new THREE.ShaderMaterial({
        glslVersion: THREE.GLSL3,
        vertexShader,
        fragmentShader: contextFragmentShader,
        uniforms: { colors: { value: texture }, uBrightness: { value: 0 } },
        transparent: true,
        depthWrite: false,
        blending: THREE.CustomBlending,
        blendEquation: THREE.MaxEquation,
      }),
    [texture],
  )

  const showContext = highlighting && contextBrightness > 0
  useEffect(() => {
    setUniform(contextMaterial, 'uBrightness', contextBrightness)
    invalidate()
  }, [contextMaterial, contextBrightness, invalidate])

  const picker = useMemo(() => {
    const mat = new THREE.ShaderMaterial({
      glslVersion: THREE.GLSL3,
      vertexShader: pickVertexShader,
      fragmentShader: pickFragmentShader,
      uniforms: { colors: { value: texture }, uPickContext: { value: 0 } },
    })
    const mesh = new THREE.LineSegments(geometry, mat)
    mesh.matrixAutoUpdate = false
    mesh.frustumCulled = false
    const scene = new THREE.Scene()
    scene.add(mesh)
    const side = 2 * PICK_RADIUS + 1
    const target = new THREE.WebGLRenderTarget(side, side)
    return { scene, mesh, target, side }
  }, [geometry, texture])

  useEffect(
    () => () => {
      geometry.dispose()
      texture.dispose()
      material.dispose()
      contextMaterial.dispose()
      picker.target.dispose()
      ;(picker.mesh.material as THREE.Material).dispose()
    },
    [geometry, texture, material, contextMaterial, picker],
  )

  // Click (not drag) on the canvas -> pick the nearest visible neuron.
  useEffect(() => {
    const el = gl.domElement
    let down: { x: number; y: number } | null = null
    const onDown = (e: PointerEvent) => {
      down = { x: e.clientX, y: e.clientY }
    }
    const onUp = (e: PointerEvent) => {
      if (!down || e.button !== 0) return
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y)
      down = null
      if (moved > CLICK_SLOP || !meshRef.current) return
      const rect = el.getBoundingClientRect()
      const index = pick(e.clientX - rect.left, e.clientY - rect.top)
      if (index !== null) onPick(index)
    }
    const pick = (x: number, y: number): number | null => {
      const { scene, mesh, target, side } = picker
      ;(mesh.material as THREE.ShaderMaterial).uniforms.uPickContext.value = showContext ? 1 : 0
      meshRef.current!.updateWorldMatrix(true, false)
      mesh.matrix.copy(meshRef.current!.matrixWorld)
      mesh.matrixWorld.copy(meshRef.current!.matrixWorld)
      const cam = camera as THREE.PerspectiveCamera
      cam.setViewOffset(size.width, size.height, x - PICK_RADIUS, y - PICK_RADIUS, side, side)
      const prevTarget = gl.getRenderTarget()
      const prevClear = gl.getClearColor(new THREE.Color())
      const prevAlpha = gl.getClearAlpha()
      gl.setRenderTarget(target)
      gl.setClearColor(0x000000, 0)
      gl.clear()
      gl.render(scene, cam)
      const pixels = new Uint8Array(side * side * 4)
      gl.readRenderTargetPixels(target, 0, 0, side, side, pixels)
      gl.setRenderTarget(prevTarget)
      gl.setClearColor(prevClear, prevAlpha)
      cam.clearViewOffset()

      let best: number | null = null
      let bestDist = Infinity
      for (let row = 0; row < side; row++) {
        for (let col = 0; col < side; col++) {
          const k = (row * side + col) * 4
          const id = pixels[k] | (pixels[k + 1] << 8) | (pixels[k + 2] << 16)
          if (id === 0) continue
          const d = (row - PICK_RADIUS) ** 2 + (col - PICK_RADIUS) ** 2
          if (d < bestDist) {
            bestDist = d
            best = id - 1
          }
        }
      }
      return best
    }
    el.addEventListener('pointerdown', onDown)
    el.addEventListener('pointerup', onUp)
    return () => {
      el.removeEventListener('pointerdown', onDown)
      el.removeEventListener('pointerup', onUp)
    }
  }, [gl, camera, size, picker, onPick, showContext])

  return (
    <>
      <lineSegments
        geometry={geometry}
        material={contextMaterial}
        scale={data.meta.unit_nm}
        frustumCulled={false}
        visible={showContext}
        renderOrder={0}
      />
      <lineSegments
        ref={meshRef}
        geometry={geometry}
        material={material}
        scale={data.meta.unit_nm}
        frustumCulled={false}
        renderOrder={1}
      />
    </>
  )
}
