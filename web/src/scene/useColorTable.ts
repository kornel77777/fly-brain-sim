import { useMemo } from 'react'
import { buildColorTable, categoryColors, partnerHighlight, type RGBA } from '../colors'
import { neuronColors } from '../sim'
import { useStore, type Detail } from '../store'

const FOCUS_ALPHA = 230
const MIN_OPACITY = 1 / 255

/** Which neurons each detail level draws (1 = drawn). */
export function detailMask(n: number, representatives: number[], detail: Detail): Uint8Array {
  const mask = new Uint8Array(n)
  if (detail === 'all') mask.fill(1)
  else if (detail === 'sketch') for (const i of representatives) mask[i] = 1
  return mask
}

/**
 * The per-neuron RGBA table for the overview, derived from the view state.
 * While a neuron, region or group is highlighted, only highlighted neurons get
 * alpha > 0; the rest go to the dim context pass (see Overview.tsx).
 */
export function useColorTable(): { table: Uint8Array; highlighting: boolean } | null {
  const attributes = useStore((s) => s.attributes)
  const colorField = useStore((s) => s.colorField)
  const opacity = useStore((s) => s.opacity)
  const focus = useStore((s) => s.focus)
  const selection = useStore((s) => s.selection)
  const showPartners = useStore((s) => s.showPartners)
  const detail = useStore((s) => s.detail)
  const region = useStore((s) => s.region)
  const simResult = useStore((s) => (s.tab === 'stimulate' ? s.sim.result : null))
  const simBin = useStore((s) => Math.floor(s.sim.bin))

  const upstream = selection?.partners.upstream
  const downstream = selection?.partners.downstream
  const selectedIndex = selection?.index

  const visible = useMemo(
    () =>
      attributes
        ? detailMask(attributes.root_ids.length, attributes.representatives, detail)
        : null,
    [attributes, detail],
  )
  // Groups (legend entries, regions) are shown at "sketch" density unless all are on.
  const groupMask = useMemo(
    () =>
      attributes
        ? detailMask(
            attributes.root_ids.length,
            attributes.representatives,
            detail === 'all' ? 'all' : 'sketch',
          )
        : null,
    [attributes, detail],
  )

  return useMemo(() => {
    if (!attributes || !visible || !groupMask) return null
    const field = attributes.fields[colorField]
    const colors = categoryColors(colorField, field.categories)
    const n = attributes.root_ids.length

    const group = (indices: Iterable<number>) => {
      const h = new Map<number, RGBA>()
      for (const i of indices) {
        if (!groupMask[i]) continue
        const code = field.codes[i]
        const c = code >= 0 ? colors[code] : [85, 85, 85]
        h.set(i, [c[0], c[1], c[2], FOCUS_ALPHA])
      }
      return h
    }
    const matching = (codes: number[], code: number) =>
      codes.flatMap((c, i) => (c === code ? [i] : []))

    let highlight: Map<number, RGBA> | null = null
    if (simResult) {
      // Simulation playback: neurons light up as they fire.
      highlight = neuronColors(simResult, Math.min(simBin, simResult.n_bins - 1))
    } else if (selectedIndex !== undefined) {
      // Partners are specific enough to show at any detail level. The selected
      // neuron itself is drawn separately at full resolution.
      highlight = partnerHighlight(
        showPartners.upstream ? (upstream ?? []) : [],
        showPartners.downstream ? (downstream ?? []) : [],
      )
    } else if (region) {
      const home = attributes.fields.home_neuropil
      highlight = group(matching(home.codes, home.categories.indexOf(region)))
    } else if (focus) {
      highlight = group(
        focus.kind === 'set' ? focus.indices : matching(field.codes, focus.code),
      )
    }
    const table = buildColorTable({
      n,
      codes: field.codes,
      colors,
      alpha: Math.max(opacity, MIN_OPACITY), // alpha 0 is reserved for context neurons
      visible,
      highlight,
      othersAlpha: 0,
    })
    return { table, highlighting: highlight !== null }
  }, [
    attributes,
    colorField,
    opacity,
    focus,
    region,
    visible,
    groupMask,
    selectedIndex,
    upstream,
    downstream,
    showPartners,
    simResult,
    simBin,
  ])
}
