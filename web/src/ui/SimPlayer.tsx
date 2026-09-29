import { useEffect } from 'react'
import { useStore } from '../store'

/** Playback is slowed down this many times relative to simulated time. */
export const SLOW_MOTION = 20

/** Advances the simulation playback clock while playing (renders nothing). */
export function SimPlayer() {
  const playing = useStore((s) => s.sim.playing)
  const setSim = useStore((s) => s.setSim)

  useEffect(() => {
    if (!playing) return
    let frame = 0
    let last = performance.now()
    const tick = (now: number) => {
      const { result, bin } = useStore.getState().sim
      if (!result) return
      const binsPerSecond = 1000 / result.bin_ms / SLOW_MOTION
      const next = bin + ((now - last) / 1000) * binsPerSecond
      last = now
      if (next >= result.n_bins - 1) {
        setSim({ bin: result.n_bins - 1, playing: false })
        return
      }
      setSim({ bin: next })
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [playing, setSim])
  return null
}
