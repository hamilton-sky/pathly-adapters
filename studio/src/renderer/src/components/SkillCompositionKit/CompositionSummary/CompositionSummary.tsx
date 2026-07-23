import React from 'react'
import styles from './CompositionSummary.module.css'

interface Props {
  bodyTokens: number
  fragTokens: number
  totalTokens: number
  includedCount: number
  allCount: number
}

/** Token-impact strip: total composed tokens + a stacked body-vs-fragments bar. */
export function CompositionSummary({ bodyTokens, fragTokens, totalTokens, includedCount, allCount }: Props): JSX.Element {
  const denom = totalTokens || 1
  const bodyShare = Math.round((bodyTokens / denom) * 100) + '%'
  const fragShare = Math.round((fragTokens / denom) * 100) + '%'
  return (
    <div className={styles.card}>
      <div className={styles.top}>
        <span className={styles.label}>Composed prompt</span>
        <span className={styles.spacer} />
        <span className={styles.total}>{totalTokens.toLocaleString()}</span>
        <span className={styles.unit}>tokens</span>
      </div>
      <div className={styles.bar}>
        <div className={styles.segBody} style={{ '--body-share': bodyShare } as React.CSSProperties} />
        <div className={styles.segFrag} style={{ '--frag-share': fragShare } as React.CSSProperties} />
      </div>
      <div className={styles.legend}>
        <span className={styles.key}><i className={styles.dotBody} />Skill body<b className={styles.num}>{bodyTokens}</b></span>
        <span className={styles.key}><i className={styles.dotFrag} />{includedCount} fragments<b className={styles.num}>{fragTokens}</b></span>
        <span className={styles.spacer} />
        <span className={styles.faint}>{includedCount} of {allCount} included</span>
      </div>
    </div>
  )
}
