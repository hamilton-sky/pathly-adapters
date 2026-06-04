import React, { useEffect, useState } from 'react'
import styles from './CatalogPanel.module.css'
import FragmentCard from './FragmentCard/FragmentCard'

interface Fragment {
  name: string
  description: string
  category: string
  requires?: string
}

export default function CatalogPanel() {
  const [fragments, setFragments] = useState<Fragment[]>([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetch('http://localhost:8765/skills/catalog')
      .then(r => r.json())
      .then(setFragments)
      .catch(() => {})
  }, [])

  const filtered = fragments.filter(f =>
    f.name.toLowerCase().includes(search.toLowerCase()) ||
    (f.description ?? '').toLowerCase().includes(search.toLowerCase())
  )

  const groups = [
    { label: 'CORE', items: filtered.filter(f => f.category === 'core') },
    { label: 'FLOW', items: filtered.filter(f => f.category === 'flow') },
    { label: 'INTEGRATION', items: filtered.filter(f => f.category === 'integration') },
  ]

  return (
    <div className={styles.root}>
      <input
        className={styles.search}
        placeholder="Search fragments…"
        value={search}
        onChange={e => setSearch(e.target.value)}
      />
      {groups.map(g => g.items.length > 0 && (
        <div key={g.label} className={styles.group}>
          <div className={styles.groupLabel}>{g.label}</div>
          {g.items.map(f => (
            <FragmentCard key={f.name} {...f} />
          ))}
        </div>
      ))}
      {filtered.length === 0 && (
        <div className={styles.empty}>No fragments found</div>
      )}
    </div>
  )
}
