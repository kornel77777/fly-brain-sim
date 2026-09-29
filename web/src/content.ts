// Explanatory text shown in the viewer. Neuropil names and groups follow the
// standard nomenclature of Ito et al. 2014 (Neuron 81:755), which FlyWire uses.

export const INTRO = {
  title: 'The wiring diagram of a fly brain',
  body:
    'This is every neuron in the brain of one adult female fruit fly, reconstructed from ' +
    'electron microscopy by the FlyWire project: about 139,000 neurons and tens of ' +
    'millions of synapses. The translucent shapes are neuropils, dense regions where ' +
    'neurons meet and exchange signals. Each has a job, from seeing and smelling to ' +
    'learning and steering.',
}

export const DETAIL_HELP = {
  regions: 'Only the brain regions.',
  sketch: 'Regions plus one example neuron of each cell type on each side (about 17,000).',
  all: 'All 139,255 neurons. Dense, but complete.',
}

export interface RegionGroup {
  id: string
  label: string
  color: string
  description: string
}

export const REGION_GROUPS: RegionGroup[] = [
  {
    id: 'optic',
    label: 'Optic lobe',
    color: '#5ab4ff',
    description:
      'Vision. Signals from the photoreceptors enter the lamina (LA), pass through the ' +
      'medulla (ME), then the lobula (LO) and lobula plate (LOP). Parallel pathways pull ' +
      'out color, the direction of motion and visual objects. The small accessory medulla ' +
      '(AME) connects with the circadian clock.',
  },
  {
    id: 'ocellar',
    label: 'Ocellar ganglion',
    color: '#ffe082',
    description:
      'Receives input from the ocelli, three simple eyes on top of the head that sense ' +
      'overall brightness and help keep the fly level in flight.',
  },
  {
    id: 'antennal_lobe',
    label: 'Antennal lobe',
    color: '#5fd38d',
    description:
      'The first stop for smell. Olfactory receptor neurons from the antennae and ' +
      'palps sort into about 50 glomeruli, one per receptor type. Projection neurons then ' +
      'carry the odor code on to the mushroom body and the lateral horn.',
  },
  {
    id: 'mushroom_body',
    label: 'Mushroom body',
    color: '#c38cff',
    description:
      'Learning and memory. Thousands of Kenyon cells receive odor input in the calyx ' +
      '(CA); their axons run through the pedunculus (PED) into the vertical and medial ' +
      'lobes (VL, ML). There, dopamine neurons signal reward or punishment and output ' +
      'neurons turn what was learned into approach or avoidance.',
  },
  {
    id: 'lateral_horn',
    label: 'Lateral horn',
    color: '#b5e36b',
    description:
      'Innate responses to smells, such as attraction to food odors or avoidance of ' +
      'danger, the hard-wired counterpart to the learned responses of the mushroom body.',
  },
  {
    id: 'central_complex',
    label: 'Central complex',
    color: '#ff9f40',
    description:
      'Navigation. The ellipsoid body (EB) holds a compass-like representation of the ' +
      "fly's heading. The protocerebral bridge (PB), fan-shaped body (FB) and noduli (NO) " +
      'combine it with self-motion and goals to decide where to steer.',
  },
  {
    id: 'lateral_complex',
    label: 'Lateral complex',
    color: '#ffc27a',
    description:
      'Links the central complex to the rest of the brain. The bulb (BU) relays visual ' +
      'and sky-compass information into the ellipsoid body, the gall (GA) connects with ' +
      'central complex outputs, and the lateral accessory lobe (LAL) is a premotor hub ' +
      'for steering.',
  },
  {
    id: 'ventrolateral',
    label: 'Ventrolateral neuropils',
    color: '#4dd0e1',
    description:
      'Higher sensory processing. Visual projection neurons from the lobula end in the ' +
      'PVLP and PLP; the anterior optic tubercle (AOTU) passes visual features toward the ' +
      'central complex; the AVLP and wedge (WED) process sound and other mechanosensory ' +
      'signals.',
  },
  {
    id: 'superior',
    label: 'Superior neuropils',
    color: '#f48fb1',
    description:
      'Integration hubs at the top of the brain (SLP, SIP, SMP). They receive output from ' +
      'the mushroom body and lateral horn, and hold many neurons involved in feeding, ' +
      'internal state and hormone release.',
  },
  {
    id: 'inferior',
    label: 'Inferior neuropils',
    color: '#b0bec5',
    description:
      'Regions around the mushroom body lobes (CRE, SCL, ICL, IB, ATL) that connect many ' +
      'parts of the brain, including the mushroom body output network.',
  },
  {
    id: 'ventromedial',
    label: 'Ventromedial neuropils',
    color: '#9fa8da',
    description:
      'The posterior slope (SPS, IPS), vest (VES), epaulette (EPA) and gorget (GOR). Many ' +
      'descending neurons, which carry commands to the body, collect their input here, ' +
      'including visual motion signals from the lobula plate.',
  },
  {
    id: 'periesophageal',
    label: 'Periesophageal neuropils',
    color: '#80cbc4',
    description:
      'Around the esophagus. The saddle (SAD) and antennal mechanosensory and motor ' +
      'center (AMMC) handle hearing, gravity and wind sensing from the antennae; the ' +
      'flange (FLA), cantle (CAN) and prow (PRW) are associated with feeding and hormonal ' +
      'signaling.',
  },
  {
    id: 'gnathal',
    label: 'Gnathal ganglia',
    color: '#ff8a80',
    description:
      'Taste and feeding. Taste neurons from the mouthparts arrive here and motor neurons ' +
      'that move the proboscis leave from here. It also links the brain to the ventral ' +
      "nerve cord, the fly's equivalent of a spinal cord.",
  },
]

const GROUP_BY_ID = Object.fromEntries(REGION_GROUPS.map((g) => [g.id, g]))

// Neuropil abbreviation (without _L/_R) -> [full name, group id]
export const NEUROPILS: Record<string, [string, string]> = {
  LA: ['Lamina', 'optic'],
  ME: ['Medulla', 'optic'],
  AME: ['Accessory medulla', 'optic'],
  LO: ['Lobula', 'optic'],
  LOP: ['Lobula plate', 'optic'],
  OCG: ['Ocellar ganglion', 'ocellar'],
  AL: ['Antennal lobe', 'antennal_lobe'],
  MB_CA: ['Mushroom body calyx', 'mushroom_body'],
  MB_PED: ['Mushroom body pedunculus', 'mushroom_body'],
  MB_VL: ['Mushroom body vertical lobe', 'mushroom_body'],
  MB_ML: ['Mushroom body medial lobe', 'mushroom_body'],
  LH: ['Lateral horn', 'lateral_horn'],
  EB: ['Ellipsoid body', 'central_complex'],
  FB: ['Fan-shaped body', 'central_complex'],
  PB: ['Protocerebral bridge', 'central_complex'],
  NO: ['Noduli', 'central_complex'],
  BU: ['Bulb', 'lateral_complex'],
  GA: ['Gall', 'lateral_complex'],
  LAL: ['Lateral accessory lobe', 'lateral_complex'],
  AOTU: ['Anterior optic tubercle', 'ventrolateral'],
  AVLP: ['Anterior ventrolateral protocerebrum', 'ventrolateral'],
  PVLP: ['Posterior ventrolateral protocerebrum', 'ventrolateral'],
  PLP: ['Posterior lateral protocerebrum', 'ventrolateral'],
  WED: ['Wedge', 'ventrolateral'],
  SLP: ['Superior lateral protocerebrum', 'superior'],
  SIP: ['Superior intermediate protocerebrum', 'superior'],
  SMP: ['Superior medial protocerebrum', 'superior'],
  CRE: ['Crepine', 'inferior'],
  SCL: ['Superior clamp', 'inferior'],
  ICL: ['Inferior clamp', 'inferior'],
  IB: ['Inferior bridge', 'inferior'],
  ATL: ['Antler', 'inferior'],
  VES: ['Vest', 'ventromedial'],
  EPA: ['Epaulette', 'ventromedial'],
  GOR: ['Gorget', 'ventromedial'],
  SPS: ['Superior posterior slope', 'ventromedial'],
  IPS: ['Inferior posterior slope', 'ventromedial'],
  SAD: ['Saddle', 'periesophageal'],
  AMMC: ['Antennal mechanosensory and motor center', 'periesophageal'],
  FLA: ['Flange', 'periesophageal'],
  CAN: ['Cantle', 'periesophageal'],
  PRW: ['Prow', 'periesophageal'],
  GNG: ['Gnathal ganglia', 'gnathal'],
}

export interface RegionInfo {
  code: string
  abbrev: string
  name: string // e.g. "Antennal lobe (right)"
  side: 'left' | 'right' | null
  group: RegionGroup
}

const FALLBACK_GROUP: RegionGroup = {
  id: 'other',
  label: 'Other',
  color: '#90a4ae',
  description: '',
}

export function regionInfo(code: string): RegionInfo {
  const m = /^(.*)_([LR])$/.exec(code)
  const abbrev = m ? m[1] : code
  const side = m ? (m[2] === 'L' ? 'left' : 'right') : null
  const entry = NEUROPILS[abbrev]
  const base = entry ? entry[0] : code
  return {
    code,
    abbrev,
    name: side ? `${base} (${side})` : base,
    side,
    group: (entry && GROUP_BY_ID[entry[1]]) || FALLBACK_GROUP,
  }
}

// What each value of a colour field means, where a short explanation helps.
export const FIELD_HELP: Record<string, { about: string; values?: Record<string, string> }> = {
  super_class: {
    about: 'The broadest grouping of neurons, by where they are and where they send signals.',
    values: {
      optic: 'Neurons within the optic lobes, processing vision.',
      central: 'Neurons within the central brain.',
      sensory: 'Carry information from sense organs (eyes, antennae, mouthparts, bristles) into the brain.',
      visual_projection: 'Carry visual information from the optic lobes into the central brain.',
      visual_centrifugal: 'Carry signals from the central brain back out to the optic lobes.',
      ascending: 'Bring information up from the ventral nerve cord in the body.',
      descending: 'Send commands from the brain down to the body, e.g. to walk, fly or groom.',
      sensory_ascending: 'Sensory neurons from the body whose axons ascend into the brain.',
      motor: 'Motor neurons: their axons leave the brain to move muscles.',
      endocrine: 'Neurosecretory cells that release hormones.',
    },
  },
  home_neuropil: {
    about: 'The brain region holding most of each neuron’s synapses.',
  },
  nt_type: {
    about:
      'The chemical each neuron releases, predicted from the electron microscopy images ' +
      '(Eckstein et al. 2024). It decides whether a neuron excites or inhibits its targets.',
    values: {
      ACH: 'Acetylcholine: the main excitatory transmitter in the fly brain.',
      GABA: 'GABA: the main inhibitory transmitter.',
      GLUT: 'Glutamate: in the fly brain often inhibitory (via glutamate-gated chloride channels).',
      DA: 'Dopamine: a neuromodulator, e.g. reward and punishment signals for learning.',
      SER: 'Serotonin: a neuromodulator linked to internal state, feeding and sleep.',
      OCT: "Octopamine: the insect counterpart of noradrenaline, for arousal and flight.",
    },
  },
  flow: {
    about: 'Whether a neuron brings signals in, sends them out, or stays within the brain.',
    values: {
      afferent: 'Brings signals into the brain (sensory and ascending neurons).',
      efferent: 'Sends signals out of the brain (descending, motor, endocrine).',
      intrinsic: 'Stays within the brain.',
    },
  },
  side: { about: 'Brain hemisphere of the cell body (or nerve entry for sensory neurons).' },
}

export const SIM_HELP = {
  intro:
    'Switch on a group of neurons and watch the signal travel through the wiring. The ' +
    'model uses the real connections of this brain and nothing else.',
  how: [
    'Each neuron is a simple unit: incoming signals charge it up, the charge slowly leaks ' +
      'away, and when it passes a threshold the neuron fires a spike.',
    'A spike excites the neurons it connects to if it releases acetylcholine, and inhibits ' +
      'them if it releases GABA or glutamate. Connections with more synapses are stronger.',
    'Stimulating means driving the chosen neurons with random spikes, much like switching ' +
      'them on with light (optogenetics) in a real experiment.',
  ],
  reading:
    'Neurons glow while they fire (brighter means faster) and leave a faint trail once ' +
    'they stop. Brain regions glow with the activity inside them. Playback is slowed down.',
  model:
    'Model: Shiu et al. 2024, Nature. It is deliberately simple: no neuromodulators, no ' +
    'learning, no body. One run with random input, so numbers vary a little between runs.',
  kenyon: (share: number) =>
    `Activity reached the mushroom body and spread through its Kenyon cells, which excite ` +
    `each other in this model (they fired ${Math.round(share * 100)}% of all spikes). In a ` +
    `real brain, feedback inhibition keeps Kenyon cell activity sparse, so treat this ` +
    `widespread wave as a limitation of the model rather than a prediction.`,
  sampled:
    'This group is larger than the model stimulates at once, so 300 of its neurons were ' +
    'picked at random.',
  rate: 'How often the stimulated neurons are made to fire, in spikes per second (Hz).',
}
