import type { Section } from './types'

export const PATHLY_SECTIONS: Section[] = [
  { label: 'Flows',     type: 'flow',     dir: 'src/pathly_data/core/flows'     },
  { label: 'Skills',    type: 'skill',    dir: 'src/pathly_data/core/skills'    },
  { label: 'Agents',    type: 'agent',    dir: 'src/pathly_data/core/agents'    },
  { label: 'Templates', type: 'template', dir: 'src/pathly_data/core/templates' },
]

export const USER_LIBRARY_SECTIONS: Section[] = [
  { label: 'UserAgents',    type: 'agent',    dir: 'agents'    },
  { label: 'UserSkills',    type: 'skill',    dir: 'skills'    },
  { label: 'UserTemplates', type: 'template', dir: 'templates' },
  { label: 'UserFlows',     type: 'flow',     dir: 'flows'     },
]

export const USER_LIBRARY_DISPLAY_LABELS: Record<string, string> = {
  UserAgents: 'Agents', UserSkills: 'Skills', UserTemplates: 'Templates', UserFlows: 'Flows',
}

export const WORKSPACE_USER_SECTIONS: Section[] = [
  { label: 'My Agents',    type: 'agent',    dir: 'pathly/agents'    },
  { label: 'My Skills',    type: 'skill',    dir: 'pathly/skills'    },
  { label: 'My Templates', type: 'template', dir: 'pathly/templates' },
  { label: 'My Flows',     type: 'flow',     dir: 'pathly/flows'     },
]

export const WORKSPACE_FILE_SECTIONS: Section[] = [
  { label: 'Debugs',               type: 'debug',   dir: 'pathly/debugs'               },
  { label: 'Explorations',         type: 'explore', dir: 'pathly/explorations'         },
  { label: 'Lessons',              type: 'explore', dir: 'pathly/lessons'              },
  { label: 'Pipeline-walkthrough', type: 'explore', dir: 'pathly/pipeline-walkthrough' },
]

export const PROTECTED_FILENAMES = new Set([
  'STATE.json',
  'EVENTS.jsonl',
  'PROGRESS.md',
  'IMPLEMENTATION_PLAN.md',
  'CONVERSATION_PROMPTS.md',
])
