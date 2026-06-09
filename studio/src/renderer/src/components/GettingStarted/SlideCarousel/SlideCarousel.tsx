import { useState, useRef, useEffect, useCallback } from 'react'
import styles from './SlideCarousel.module.css'

interface Slide {
  readonly file: string
  readonly name: string
}

interface Props {
  dsPort: number | null
  slides: ReadonlyArray<Slide>
}

const AUTO_MS = 5500

export function SlideCarousel({ dsPort, slides }: Props): JSX.Element {
  const [idx, setIdx] = useState(0)
  const [dir, setDir] = useState<'next' | 'prev'>('next')
  const [loaded, setLoaded] = useState(false)
  const [paused, setPaused] = useState(false)
  const viewportRef = useRef<HTMLDivElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)

  const go = useCallback((next: number): void => {
    if (next === idx) return
    setDir(next > idx ? 'next' : 'prev')
    setLoaded(false)
    setIdx(next)
  }, [idx])

  const goNext = useCallback(() => go((idx + 1) % slides.length), [go, idx, slides.length])
  const goPrev = useCallback(() => go((idx - 1 + slides.length) % slides.length), [go, idx, slides.length])

  // Auto-advance
  useEffect(() => {
    if (paused) return undefined
    const t = setTimeout(goNext, AUTO_MS)
    return () => clearTimeout(t)
  }, [idx, paused, goNext])

  // Keyboard navigation
  useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      if (e.key === 'ArrowRight') goNext()
      else if (e.key === 'ArrowLeft') goPrev()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [goNext, goPrev])

  // Viewport width → --scale CSS custom property
  useEffect(() => {
    const el = viewportRef.current
    if (!el) return undefined
    const ro = new ResizeObserver(([entry]) => {
      el.style.setProperty('--scale', String(entry.contentRect.width / 1280))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Progress bar → --progress CSS custom property
  useEffect(() => {
    progressRef.current?.style.setProperty('--progress', `${((idx + 1) / slides.length) * 100}%`)
  }, [idx, slides.length])

  const iframeKey = `${idx}-${dsPort}`

  return (
    <div
      className={styles.wrapper}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className={styles.headerRow}>
        <span className={styles.eyebrow}>SEE PATHLY</span>
        <span className={styles.counter}>
          {idx + 1}
          <span className={styles.counterSep}> / </span>
          {slides.length}
        </span>
      </div>

      <div className={styles.frame}>
        <div className={styles.progressTrack}>
          <div ref={progressRef} className={styles.progressBar} />
        </div>

        <div ref={viewportRef} className={styles.viewport}>
          {!loaded && <div className={styles.shimmer} />}
          <div
            className={`${styles.slideWrapper} ${loaded ? styles.slideVisible : ''}`}
            data-dir={dir}
          >
            <iframe
              key={iframeKey}
              src={dsPort ? `http://127.0.0.1:${dsPort}/slides/${slides[idx].file}` : 'about:blank'}
              title={slides[idx].name}
              onLoad={() => { if (dsPort !== null) setLoaded(true) }}
              className={styles.slide}
            />
          </div>
        </div>

        <div className={styles.navBar}>
          <button type="button" aria-label="Previous slide" onClick={goPrev} className={styles.navBtn}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M8 2.5L4.5 6L8 9.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          <div className={styles.navCenter}>
            <span className={styles.slideName}>{slides[idx].name}</span>
            <div className={styles.dots} role="tablist" aria-label="Slides">
              {slides.map((s, i) => (
                <button
                  key={s.file}
                  type="button"
                  role="tab"
                  aria-label={`Go to ${s.name}`}
                  {...(i === idx ? { 'aria-selected': 'true' } : { 'aria-selected': 'false' })}
                  onClick={() => go(i)}
                  className={`${styles.dot} ${i === idx ? styles.dotActive : ''}`}
                />
              ))}
            </div>
          </div>

          <button type="button" aria-label="Next slide" onClick={goNext} className={styles.navBtn}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M4 2.5L7.5 6L4 9.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
