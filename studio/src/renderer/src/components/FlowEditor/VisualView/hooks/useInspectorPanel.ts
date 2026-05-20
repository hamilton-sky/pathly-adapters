import { useState } from 'react'
import type { PanelDetail } from '../constants'

export function useInspectorPanel() {
  const [detail, setDetail] = useState<PanelDetail>(null)
  return { detail, setDetail }
}
