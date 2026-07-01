import React from 'react';
import { CommsProvider } from './useCommsStore';
import { CommandCenter } from './CommandCenter';

// ── Entry ───────────────────────────────────────────────────────────
// Standalone demo entry for the kit. Tokens (styles.css), command-center.css,
// and React/ReactDOM (UMD) are provided by the host page.
//
// In Studio (Vite), import React DOM idiomatically instead:
//   import { createRoot } from 'react-dom/client';
//   import './command-center.css';
//   createRoot(el).render(<CommsProvider><CommandCenter/></CommsProvider>);

declare const ReactDOM: { createRoot: (el: Element) => { render: (node: React.ReactNode) => void } };

export function mount(el: Element) {
  ReactDOM.createRoot(el).render(
    <CommsProvider>
      <CommandCenter />
    </CommsProvider>,
  );
}

const host = typeof document !== 'undefined' && document.getElementById('cc-root');
if (host) mount(host);
