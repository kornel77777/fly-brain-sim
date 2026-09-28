import { useMemo } from 'react'
import { buildColorTable, categoryColors, partnerHighlight, type RGBA } from '../colors'
import { useStore } from '../store'

const FOCUS_ALPHA = 230
const MIN_OPACITY = 1 / 255

/**
 * The per-neuron RGBA table for the overview, derived from the view state.
 * While a neuron is selected or a set is focused, only highlighted neurons get
 * alpha > 0; everything else goes to the dim context pass (see Overview.tsx).
 */
export function useColorTable(): { table: Uint8Array; highlighting: boolean } | null {
  const attributes = useStore((s) => s.attributes)
  const colorField = useStore((s) => s.colorField)
  const opacity = useStore((s) => s.opacity)
  const focus = useStore((s) => s.focus)
  const selection = useStore((s) => s.selection)
  const showPartners = useStore((s) => s.showPartners)

  const upstream = selection?.partners.upstream
  const downstream = selection?.partners.downstream
  const selectedIndex = selection?.index

  return useMemo(() => {
    if (!attributes) return null
    const field = attributes.fields[colorField]
    const colors = categoryColors(colorField, field.categories)
    const n = attributes.root_ids.length

    let highlight: Map<number, RGBA> | null = null
    if (selectedIndex !== undefined) {
      highlight = partnerHighlight(
        showPartners.upstream ? (upstream ?? []) : [],
        showPartners.downstream ? (downstream ?? []) : [],
      )
      // The selected neuron is drawn separately at full resolution; keep its
      // overview copy in the (dim) context pass.
    } else if (focus) {
      highlight = new Map()
      const indices =
        focus.kind === 'set'
          ? focus.indices
          : field.codes.flatMap((c, i) => (c === focus.code ? [i] : []))
      for (const i of indices) {
        const code = field.codes[i]
        const c = code >= 0 ? colors[code] : [85, 85, 85]
        highlight.set(i, [c[0], c[1], c[2], FOCUS_ALPHA])
      }
    }
    const table = buildColorTable({
      n,
      codes: field.codes,
      colors,
      alpha: Math.max(opacity, MIN_OPACITY), // alpha 0 is reserved for context neurons
      highlight,
      othersAlpha: 0,
    })
    return { table, highlighting: highlight !== null }
  }, [attributes, colorField, opacity, focus, selectedIndex, upstream, downstream, showPartners])
}
