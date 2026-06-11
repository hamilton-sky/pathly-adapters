import React from 'react';

// ── Icon ────────────────────────────────────────────────────────────
// Thin wrapper over the self-hosted lucide subset (assets/vendor/icons.js,
// exposed as window.PathlyIcons). In Studio, swap for `lucide-react`.

declare global {
  interface Window {
    PathlyIcons?: { svg: (name: string, opts?: { size?: number; strokeWidth?: number }) => string };
  }
}

export interface IconProps {
  name: string;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function Icon({ name, size = 14, className, style }: IconProps) {
  const html = (typeof window !== 'undefined' && window.PathlyIcons)
    ? window.PathlyIcons.svg(name, { size })
    : '';
  return (
    <span
      className={className}
      style={{ display: 'inline-flex', ...style }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
