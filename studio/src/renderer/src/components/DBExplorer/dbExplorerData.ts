export type PipelineState =
  | 'PLANNING'
  | 'BUILDING'
  | 'REVIEWING'
  | 'TESTING'
  | 'RETRO'
  | 'DONE'

interface DotSegment {
  state: PipelineState
  flex?: number
}

interface FeatureData {
  name: string
  state: PipelineState
  events: number
  inv: number
  tokens: string
  cost: string
  ts: string
  pcol: string
  dots: DotSegment[]
}

export interface TransitionData {
  state: PipelineState
  time: string
  duration: string
}

interface AgentData {
  role: string
  conv: string
  stateColor: string
  costFraction: number
}

interface EventData {
  time: string
  type: string
  detail: string
  dotColor: string
}

const FEATURES: FeatureData[] = [
  {
    name: 'fsm-sqlite',
    state: 'DONE',
    events: 35,
    inv: 8,
    tokens: '290,749',
    cost: '$3.64',
    ts: '10:06:05',
    pcol: 'var(--state-done)',
    dots: [
      { state: 'BUILDING' },
      { state: 'REVIEWING' },
      { state: 'BUILDING' },
      { state: 'TESTING' },
      { state: 'REVIEWING' },
      { state: 'BUILDING' },
      { state: 'TESTING' },
      { state: 'REVIEWING' },
      { state: 'DONE', flex: 1.4 },
    ],
  },
  {
    name: 'auth-refactor',
    state: 'BUILDING',
    events: 23,
    inv: 4,
    tokens: '142,300',
    cost: '$1.97',
    ts: '11:14:02',
    pcol: 'var(--state-building)',
    dots: [
      { state: 'PLANNING' },
      { state: 'BUILDING' },
      { state: 'BUILDING', flex: 1.6 },
      { state: 'REVIEWING' },
    ],
  },
  {
    name: 'payments-webhook',
    state: 'REVIEWING',
    events: 28,
    inv: 6,
    tokens: '188,400',
    cost: '$2.41',
    ts: '09:31:50',
    pcol: 'var(--state-reviewing)',
    dots: [
      { state: 'BUILDING' },
      { state: 'REVIEWING' },
      { state: 'BUILDING' },
      { state: 'TESTING' },
      { state: 'REVIEWING', flex: 1.5 },
    ],
  },
  {
    name: 'search-index',
    state: 'TESTING',
    events: 19,
    inv: 5,
    tokens: '96,800',
    cost: '$1.12',
    ts: '13:20:11',
    pcol: 'var(--state-testing)',
    dots: [
      { state: 'BUILDING' },
      { state: 'REVIEWING' },
      { state: 'TESTING', flex: 1.6 },
    ],
  },
  {
    name: 'cache-layer',
    state: 'DONE',
    events: 41,
    inv: 9,
    tokens: '214,600',
    cost: '$3.02',
    ts: '08:48:33',
    pcol: 'var(--state-done)',
    dots: [
      { state: 'BUILDING' },
      { state: 'REVIEWING' },
      { state: 'TESTING' },
      { state: 'BUILDING' },
      { state: 'REVIEWING' },
      { state: 'RETRO' },
      { state: 'DONE', flex: 1.4 },
    ],
  },
  {
    name: 'notifications',
    state: 'PLANNING',
    events: 6,
    inv: 1,
    tokens: '18,900',
    cost: '$0.31',
    ts: '14:02:19',
    pcol: 'var(--state-planning)',
    dots: [{ state: 'PLANNING', flex: 2 }],
  },
]

const TRANSITIONS: TransitionData[] = [
  { state: 'PLANNING', time: '09:02:11', duration: '6m 29s' },
  { state: 'BUILDING', time: '09:08:40', duration: '12m 26s' },
  { state: 'REVIEWING', time: '09:21:06', duration: '6m 27s' },
  { state: 'TESTING', time: '09:27:33', duration: '6m 45s' },
  { state: 'BUILDING', time: '09:34:18', duration: '11m 44s' },
  { state: 'REVIEWING', time: '09:46:02', duration: '6m 47s' },
  { state: 'TESTING', time: '09:52:49', duration: '4m 38s' },
  { state: 'RETRO', time: '09:57:27', duration: '3m 12s' },
  { state: 'DONE', time: '10:06:05', duration: '—' },
]

const AGENTS: AgentData[] = [
  { role: 'builder', conv: 'conv 1', stateColor: 'var(--state-building)', costFraction: 0.39 },
  { role: 'reviewer', conv: 'conv 1', stateColor: 'var(--state-reviewing)', costFraction: 0.71 },
  { role: 'builder', conv: 'conv 2', stateColor: 'var(--state-building)', costFraction: 0.42 },
  { role: 'tester', conv: 'conv 2', stateColor: 'var(--state-testing)', costFraction: 0.23 },
  { role: 'reviewer', conv: 'conv 2', stateColor: 'var(--state-reviewing)', costFraction: 0.74 },
  { role: 'builder', conv: 'conv 3', stateColor: 'var(--state-building)', costFraction: 0.33 },
  { role: 'tester', conv: 'conv 3', stateColor: 'var(--state-testing)', costFraction: 0.24 },
  { role: 'reviewer', conv: 'conv 3', stateColor: 'var(--state-reviewing)', costFraction: 0.58 },
]

const EVENTS: EventData[] = [
  { time: '09:02:11', type: 'STAGE_ENTER', detail: 'PLANNING', dotColor: 'var(--state-building)' },
  { time: '09:08:40', type: 'AGENT_DONE', detail: 'builder · $0.39', dotColor: 'var(--state-done)' },
  { time: '09:21:06', type: 'STAGE_ENTER', detail: 'REVIEWING', dotColor: 'var(--state-reviewing)' },
  { time: '09:34:18', type: 'STAGE_REROUTE', detail: '→ BUILDING', dotColor: 'var(--orange)' },
  { time: '10:06:05', type: 'PIPELINE_DONE', detail: '290,749 tok · $3.64', dotColor: 'var(--state-done)' },
]
