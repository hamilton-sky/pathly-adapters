import type { Feature, Boards } from './types';

// ── Seed data ───────────────────────────────────────────────────────
// Demo roster + boards. In Studio these come from the FSM over SSE
// (GET /events/comms) and GET /comms — see SPEC §10.

let n = 0;
const id = () => `m${++n}`;

export const SEED_FEATURES: Feature[] = [
  { id: 'send-to-agent-diff', stage: 'BUILDING', conv: 3, status: 'running', agent: 'builder',
    last: '<b>builder:</b> phases 7–9 complete. Wiring DiffViewer scroll sync.',
    scope: { feature: true, project: true, global: true } },
  { id: 'comms-board', stage: 'PLANNING', conv: 1, status: 'idle', agent: 'architect',
    last: '<b>architect:</b> drafting comms_messages + sqlite-vec schema.',
    scope: { feature: true, project: true, global: true } },
  { id: 'event-phase-summary', stage: 'REVIEWING', conv: 2, status: 'blocked', agent: 'reviewer',
    last: '<b>reviewer:</b> 3 failures — missing null guards in summary writer.',
    scope: { feature: true, project: true, global: false } },
  { id: 'otel-export-cli', stage: 'DONE', conv: 4, status: 'done', agent: 'retro',
    last: '<b>retro:</b> archived. 64.8k tok · $3.64 · 6m 29s.',
    scope: { feature: true, project: true, global: true } },
];

export const SEED_BOARDS: Boards = {
  'send-to-agent-diff': [
    { id: id(), type: 'decision', from: 'you', stage: 'REVIEWING', time: '2h', pinned: true,
      text: 'Skip rename detection — that is v2 scope.' },
    { id: id(), type: 'status', from: 'builder', stage: 'BUILDING', time: '8m',
      text: 'Phases 7–9 complete. <code>DiffViewer.tsx</code> created. Starting scroll-sync.' },
    { id: id(), type: 'discovery', from: 'builder', stage: 'BUILDING', time: '6m',
      text: 'Virtual scroll is needed when a diff exceeds ~500 lines, or the panes jank.' },
    { id: id(), type: 'question', from: 'builder', stage: 'BUILDING', time: '4m', status: 'pending',
      text: 'Two approaches for scroll sync between the diff panes. Preference?',
      options: [
        { id: 'a', label: 'CSS scroll-snap', desc: 'simple, native' },
        { id: 'b', label: 'JS IntersectionObserver', desc: 'more control' },
      ] },
  ],
  'comms-board': [
    { id: id(), type: 'decision', from: 'you', stage: 'PLANNING', time: '1h', pinned: true,
      text: 'Embeddings: <code>all-MiniLM-L6-v2</code>, 384-dim. No external API cost.' },
    { id: id(), type: 'status', from: 'architect', stage: 'PLANNING', time: '12m',
      text: 'Schema drafted: <code>comms_messages</code> + <code>comms_embeddings</code> (vec0).' },
  ],
  'event-phase-summary': [
    { id: id(), type: 'warning', from: 'reviewer', stage: 'REVIEWING', time: '3m', status: 'open',
      text: 'Rename detection missing and 2 null-guard failures in the summary writer.' },
  ],
  'otel-export-cli': [
    { id: id(), type: 'status', from: 'retro', stage: 'RETRO', time: '1d',
      text: 'Run archived. Lessons written to <code>pathly/lessons/</code>.' },
  ],
  project: [
    { id: id(), type: 'decision', from: 'you', time: '4d', pinned: true, text: 'Use <code>shadcn/ui</code> for all new components.' },
    { id: id(), type: 'decision', from: 'you', time: '4d', pinned: true, text: 'Auth is handled by <code>/lib/auth.ts</code> — never roll custom auth.' },
    { id: id(), type: 'decision', from: 'you', time: '6d', pinned: true, text: 'TypeScript <code>strict</code> mode across the repo.' },
    { id: id(), type: 'artifact', from: 'you', time: '3d', artifact: 'ARCHITECTURE.md', atype: 'md',
      text: 'Adapter surfaces per host, deployment structure, host detection, installed manifests…' },
    { id: id(), type: 'status', from: 'reviewer', stage: 'REVIEWING', time: '20m', text: 'Found 2 issues in <code>event-phase-summary</code>; surfaced to its board.' },
  ],
  global: [
    { id: id(), type: 'decision', from: 'you', time: '2w', pinned: true, text: 'Use <code>Zod</code> for all schema validation.' },
    { id: id(), type: 'decision', from: 'you', time: '3w', pinned: true, text: 'No class components anywhere in the org.' },
    { id: id(), type: 'decision', from: 'you', time: '5w', pinned: true, text: 'All user-facing errors must include an error code.' },
    { id: id(), type: 'artifact', from: 'you', time: '5w', artifact: 'auth-pattern.ts', atype: 'code',
      text: 'export async function withAuth(req: Request) { /* always use this pattern */ }' },
  ],
};

export const nextId = id;
