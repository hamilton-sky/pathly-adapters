import React from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { useToastStore } from '../../store/toastStore'
import { useNotificationStore } from '../../store/notificationStore'
import type { ToastPosition, ToastStyle } from '../../store/notificationStore'
import styles from './Toaster.module.css'

const POS_CLASS: Record<ToastPosition, string> = {
  'bottom-right': styles.posBottomRight,
  'bottom-left':  styles.posBottomLeft,
  'top-right':    styles.posTopRight,
  'top-left':     styles.posTopLeft,
}

const STYLE_CLASS: Record<ToastStyle, string> = {
  'default': styles.styleDefault,
  'card':    styles.styleCard,
  'minimal': styles.styleMinimal,
  'banner':  styles.styleBanner,
}

export function Toaster(): JSX.Element {
  const { toasts, remove } = useToastStore()
  const position = useNotificationStore((s) => s.position)
  const toastStyle = useNotificationStore((s) => s.style)
  const isBanner = toastStyle === 'banner'
  const isTop = position.startsWith('top')

  const containerClass = [
    styles.container,
    POS_CLASS[position],
    isBanner ? (isTop ? styles.containerBannerTop : styles.containerBannerBottom) : '',
  ].filter(Boolean).join(' ')

  return createPortal(
    <div className={containerClass}>
      {toasts.map((t) => (
        <div
          key={t.id}
          className={[styles.toast, styles[t.variant], STYLE_CLASS[toastStyle], isTop ? styles.animateDown : ''].filter(Boolean).join(' ')}
          {...(t.accentColor ? { style: { '--toast-accent': t.accentColor } as React.CSSProperties } : {})}
        >
          <span className={styles.message}>{t.message}</span>
          <button type="button" className={styles.close} onClick={() => remove(t.id)} aria-label="Dismiss">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>,
    document.body
  )
}
