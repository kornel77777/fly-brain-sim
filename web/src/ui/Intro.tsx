import { useState } from 'react'
import { INTRO } from '../content'

const KEY = 'fly-brain-intro-hidden'

function readHidden(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

/** A short "what am I looking at" card; the viewer remembers if it was dismissed. */
export function Intro() {
  const [hidden, setHidden] = useState(readHidden)
  const toggle = (value: boolean) => {
    setHidden(value)
    try {
      localStorage.setItem(KEY, value ? '1' : '0')
    } catch {
      // storage unavailable (private mode); the choice just isn't remembered
    }
  }
  if (hidden) {
    return (
      <button className="link small intro-toggle" onClick={() => toggle(false)}>
        What am I looking at?
      </button>
    )
  }
  return (
    <div className="intro">
      <strong>{INTRO.title}</strong>
      <p>{INTRO.body}</p>
      <p>
        Drag to rotate, scroll to zoom. Click a region or a neuron to learn about it.
      </p>
      <button className="link small" onClick={() => toggle(true)}>
        Got it
      </button>
    </div>
  )
}
