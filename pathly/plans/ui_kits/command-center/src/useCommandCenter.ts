import { useState, useCallback } from 'react';
import type { BoardScope, CommandCenterState, Direction, Preset } from './types';

// ── useCommandCenter ────────────────────────────────────────────────
// Workspace UI state: which board sections are visible, layout direction,
// preset, the main feature, sidebar + accordion. Persist to localStorage
// in Studio (key: `pathly-command-center-layout`).

const PRESETS: Record<Exclude<Preset, 'custom'>, Partial<CommandCenterState>> = {
  board:    { sections: ['global', 'project', 'feature'], direction: 'row', sidebarCollapsed: false },
  pipeline: { sections: ['feature'], direction: 'row', sidebarCollapsed: false },
  focus:    { sections: ['feature'], direction: 'row', sidebarCollapsed: true },
};

const INITIAL: CommandCenterState = {
  sections: ['feature'],
  direction: 'row',
  preset: 'focus',
  mainFeature: 'send-to-agent-diff',
  sidebarCollapsed: false,
  openFeature: 'send-to-agent-diff',
  sizes: {},
};

export function useCommandCenter(initial: Partial<CommandCenterState> = {}) {
  const [s, set] = useState<CommandCenterState>({ ...INITIAL, ...initial });

  const applyPreset = useCallback((preset: Exclude<Preset, 'custom'>) => {
    const p = PRESETS[preset];
    set((prev) => ({ ...prev, ...p, preset, sections: p.sections!.slice(), sizes: {} }));
  }, []);

  const toggleSection = useCallback((scope: BoardScope) => {
    set((prev) => {
      const i = prev.sections.indexOf(scope);
      const sections = i > -1
        ? prev.sections.filter((x) => x !== scope)
        : [...prev.sections, scope];
      return { ...prev, sections, preset: 'custom', sizes: {} };
    });
  }, []);

  const addAnySection = useCallback(() => {
    set((prev) => {
      const missing = (['feature', 'project', 'global'] as BoardScope[])
        .find((x) => prev.sections.indexOf(x) < 0);
      if (!missing) return prev;
      return { ...prev, sections: [...prev.sections, missing], preset: 'custom' };
    });
  }, []);

  const toggleDirection = useCallback(() => {
    set((prev) => ({ ...prev, direction: (prev.direction === 'row' ? 'column' : 'row') as Direction, sizes: {} }));
  }, []);

  const setMainFeature = useCallback((fid: string) => {
    set((prev) => ({
      ...prev,
      mainFeature: fid,
      sections: prev.sections.indexOf('feature') < 0 ? [...prev.sections, 'feature'] : prev.sections,
    }));
  }, []);

  const openFeatureFromRail = useCallback((fid: string) => {
    set((prev) => ({
      ...prev,
      mainFeature: fid,
      openFeature: fid,
      sidebarCollapsed: false,
      sections: prev.sections.indexOf('feature') < 0 ? [...prev.sections, 'feature'] : prev.sections,
    }));
  }, []);

  const toggleOpenFeature = useCallback((fid: string) => {
    set((prev) => ({ ...prev, openFeature: prev.openFeature === fid ? null : fid }));
  }, []);

  const toggleSidebar = useCallback(() => set((prev) => ({ ...prev, sidebarCollapsed: !prev.sidebarCollapsed })), []);

  const setSize = useCallback((scope: BoardScope, px: number) => {
    set((prev) => ({ ...prev, sizes: { ...prev.sizes, [scope]: px } }));
  }, []);

  return {
    state: s,
    applyPreset, toggleSection, addAnySection, toggleDirection,
    setMainFeature, openFeatureFromRail, toggleOpenFeature, toggleSidebar, setSize,
  };
}

export type CommandCenterApi = ReturnType<typeof useCommandCenter>;
