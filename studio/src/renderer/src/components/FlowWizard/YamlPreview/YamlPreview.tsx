import styles from './YamlPreview.module.css'

interface YamlPreviewProps {
  yaml: string
}

export function YamlPreview({ yaml }: YamlPreviewProps): JSX.Element {
  return (
    <div className={styles.card}>
      <div className={styles.title}>Live YAML</div>
      <div className={styles.sub}>Updates as you edit the wizard.</div>
      <pre className={styles.pre}>{yaml}</pre>
    </div>
  )
}
