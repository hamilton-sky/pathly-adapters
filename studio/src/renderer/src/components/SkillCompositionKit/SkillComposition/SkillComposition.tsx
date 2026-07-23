import { useState } from 'react'
import { useProjectPath } from '../integration'
import { useSkillCompositionCatalog } from '../hooks/useSkillCompositionCatalog'
import { SkillSidebar } from '../SkillSidebar/SkillSidebar'
import { FragmentPanel } from '../FragmentPanel/FragmentPanel'
import styles from './SkillComposition.module.css'

/** Skill Composition panel — per-project fragment overrides with a live composed-prompt preview. */
export function SkillComposition(): JSX.Element {
  const projectRoot = useProjectPath()
  const { catalog, loading, error, selectedSkill, setSelectedSkill, refetch } =
    useSkillCompositionCatalog(projectRoot)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div className={styles.headText}>
          <h2 className={styles.title}>Skill Composition</h2>
          <span className={styles.subtitle}>Per-project fragment overrides — live composed-prompt preview</span>
        </div>
        <div className={styles.spacer} />
        <span className={styles.live}><i className={styles.liveDot} />server live</span>
      </div>

      <div className={styles.body}>
        <SkillSidebar
          skills={catalog?.skills ?? {}}
          selectedSkill={selectedSkill}
          onSelect={setSelectedSkill}
          loading={loading}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
        />

        <div className={styles.rightPane}>
          {error && <div className={styles.error}>{error}</div>}
          {!error && catalog && selectedSkill && (
            <FragmentPanel
              key={selectedSkill}
              skill={selectedSkill}
              entry={catalog.skills[selectedSkill]}
              allFragments={catalog.all_fragments}
              projectRoot={projectRoot}
              onChanged={refetch}
            />
          )}
          {!error && !loading && !selectedSkill && (
            <div className={styles.empty}>Select a skill to view its fragment composition</div>
          )}
        </div>
      </div>
    </div>
  )
}
