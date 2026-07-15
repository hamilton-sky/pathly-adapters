import { useState } from 'react'
import { useProjectStore } from '../../store/projectStore'
import { useSkillCompositionCatalog } from './hooks/useSkillCompositionCatalog'
import { SkillSidebar } from './SkillSidebar/SkillSidebar'
import { FragmentPanel } from './FragmentPanel/FragmentPanel'
import styles from './SkillComposition.module.css'

export function SkillComposition(): JSX.Element {
  const projectRoot = useProjectStore((s) => s.projectPath)
  const { catalog, loading, error, selectedSkill, setSelectedSkill, refetch } =
    useSkillCompositionCatalog(projectRoot)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <h2 className={styles.title}>Skill Composition</h2>
        <span className={styles.subtitle}>Per-project fragment overrides — live composed-prompt preview</span>
      </div>

      <div className={styles.body}>
        <div className={styles.leftPane} data-collapsed={sidebarCollapsed}>
          <SkillSidebar
            skills={catalog?.skills ?? {}}
            selectedSkill={selectedSkill}
            onSelect={setSelectedSkill}
            loading={loading}
            collapsed={sidebarCollapsed}
            onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
          />
        </div>

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
