import React, { createContext, useContext, useState, useCallback } from 'react';
import type { Boards, Feature, Message, BoardScope, MessageType, FeatureStatus, Stage } from './types';
import { SEED_BOARDS, SEED_FEATURES, nextId } from './seed';

// ── Comms store ─────────────────────────────────────────────────────
// Single source of truth for features + boards and the actions that mutate
// them. Framework-agnostic (plain React context) so it drops into Studio;
// swap the internals for zustand/`chatStore.ts` without touching consumers.

function isPending(m: Message): boolean {
  return (m.type === 'question' && m.status === 'pending')
    || (m.type === 'warning' && m.status === 'open')
    || m.type === 'escalation';
}

export interface CommsStore {
  features: Feature[];
  boards: Boards;
  /** count of items needing attention on a feature board */
  pendingCount: (featureId: string) => number;
  /** messages for a board scope (feature scope resolves via mainFeature) */
  messagesFor: (scope: BoardScope, mainFeature: string) => Message[];
  /** appends a message; returns the new message id */
  post: (key: string, type: MessageType, text: string, stage?: Stage | null) => string;
  answer: (featureId: string, messageId: string, optionId: string) => void;
  resolve: (messageId: string, mode: 'block' | 'note' | 'ignore') => void;
  setFeatureStatus: (featureId: string, status: FeatureStatus, stage?: Stage) => void;
  toggleScope: (featureId: string, scope: BoardScope) => void;
}

const Ctx = createContext<CommsStore | null>(null);

export function CommsProvider({ children }: { children: React.ReactNode }) {
  const [features, setFeatures] = useState<Feature[]>(() => SEED_FEATURES.map((f) => ({ ...f })));
  const [boards, setBoards] = useState<Boards>(() => structuredCloneSafe(SEED_BOARDS));

  const pendingCount = useCallback(
    (fid: string) => (boards[fid] || []).filter(isPending).length,
    [boards],
  );

  const messagesFor = useCallback(
    (scope: BoardScope, mainFeature: string) =>
      boards[scope === 'feature' ? mainFeature : scope] || [],
    [boards],
  );

  const patchFeature = useCallback((fid: string, patch: Partial<Feature>) => {
    setFeatures((fs) => fs.map((f) => (f.id === fid ? { ...f, ...patch } : f)));
  }, []);

  const setFeatureStatus = useCallback<CommsStore['setFeatureStatus']>((fid, status, stage) => {
    patchFeature(fid, stage ? { status, stage } : { status });
    if (status === 'running') {
      // unblocking clears an open warning on that board
      setBoards((b) => ({
        ...b,
        [fid]: (b[fid] || []).map((m) =>
          m.type === 'warning' && m.status === 'open'
            ? { ...m, status: 'resolved', resolution: 'unblocked → builder retry' }
            : m),
      }));
    }
  }, [patchFeature]);

  const post = useCallback<CommsStore['post']>((key, type, text, stage) => {
    const m: Message = {
      id: nextId(), type, from: 'you', time: 'now', text,
      stage: stage ?? null, pinned: type === 'decision',
      ...(type === 'question'
        ? { status: 'pending', options: [{ id: 'a', label: 'Option A' }, { id: 'b', label: 'Option B' }] }
        : {}),
    };
    setBoards((b) => ({ ...b, [key]: [...(b[key] || []), m] }));
    return m.id;
  }, []);

  const answer = useCallback<CommsStore['answer']>((fid, mid, opt) => {
    setBoards((b) => {
      const arr = b[fid] || [];
      const q = arr.find((m) => m.id === mid);
      if (!q || q.status === 'answered') return b;
      const chosen = (q.options || []).find((o) => o.id === opt);
      const next = arr.map((m) => (m.id === mid ? { ...m, status: 'answered' as const, answer: opt } : m));
      next.push({
        id: nextId(), type: 'answer', from: 'you', stage: q.stage, time: 'now',
        text: `Use <code>${chosen?.label}</code>. Keep it simple.`,
      });
      next.push({
        id: nextId(), type: 'status', from: 'builder', stage: q.stage, time: 'now', ack: true,
        text: `Got it — implementing <code>${chosen?.label}</code>.`,
      });
      return { ...b, [fid]: next };
    });
  }, []);

  const resolve = useCallback<CommsStore['resolve']>((mid, mode) => {
    setBoards((b) => {
      const key = Object.keys(b).find((k) => (b[k] || []).some((m) => m.id === mid));
      if (!key) return b;
      const resolution =
        mode === 'block' ? 'blocked → RETRY (builder)'
        : mode === 'note' ? 'noted as v2 → REVIEWING advances'
        : 'ignored → REVIEWING advances';
      const arr = (b[key] || []).map((m) => (m.id === mid ? { ...m, status: 'resolved' as const, resolution } : m));
      if (mode === 'note') {
        arr.push({
          id: nextId(), type: 'decision', from: 'you', stage: 'REVIEWING', time: 'now', pinned: true,
          text: 'Rename detection is v2 scope. Do not block.',
        });
      }
      // advance / retry the owning feature
      setFeatureStatus(key, 'running', mode === 'block' ? 'BUILDING' : 'TESTING');
      return { ...b, [key]: arr };
    });
  }, [setFeatureStatus]);

  const toggleScope = useCallback<CommsStore['toggleScope']>((fid, scope) => {
    setFeatures((fs) => fs.map((f) =>
      f.id === fid ? { ...f, scope: { ...f.scope, [scope]: !f.scope[scope] } } : f));
  }, []);

  const store: CommsStore = {
    features, boards, pendingCount, messagesFor,
    post, answer, resolve, setFeatureStatus, toggleScope,
  };
  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}

export function useCommsStore(): CommsStore {
  const s = useContext(Ctx);
  if (!s) throw new Error('useCommsStore must be used within <CommsProvider>');
  return s;
}

function structuredCloneSafe(b: Boards): Boards {
  const out: Boards = {};
  for (const k of Object.keys(b)) out[k] = b[k].map((m) => ({ ...m }));
  return out;
}
