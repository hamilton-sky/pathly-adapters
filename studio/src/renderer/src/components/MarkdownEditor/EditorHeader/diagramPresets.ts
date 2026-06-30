// Diagram style presets — the six options shown in PromptPeekModal.
// Two groups: "Renders anywhere" (Mermaid + ASCII, no engine needed) and
// "Needs render engine" (PlantUML, source-only until an engine is bundled).
//
// {{FILE}} and {{SIDECAR}} are resolved at spawn time by resolvePrompt()
// (see shared/PromptActionConfig/presetTypes.ts).

import type { PromptPreset } from '../../shared/PromptActionConfig/presetTypes'
import type { DiagramStyle } from '../diagramTypes'

// localStorage keys — parallel to CLI_KEY_SPLIT / PRESET_KEY_SPLIT in editorCli.ts.
export const CLI_KEY_DIAGRAM = 'pathly.notebook.cli.diagram'
export const PRESET_KEY_DIAGRAM = 'pathly.notebook.preset.diagram'
export const STORAGE_KEY_DIAGRAM = 'pathly.notebook.prompt.diagram'

export interface DiagramPreset extends PromptPreset {
  /** Which renderer this preset targets. */
  style: DiagramStyle
  /** UI grouping. */
  group: 'anywhere' | 'engine'
  /** Shown as a warning chip when the render engine is not yet bundled. */
  unavailable?: string
}

/** Shared tail every diagram prompt ends with — defines the append contract. */
const APPEND_CONTRACT = [
  ``,
  `Append exactly ONE JSON object to the array at {{SIDECAR}} (create the file with`,
  `{ "version": 1, "source": "<this file>", "diagrams": [] } if it does not exist).`,
  `The object must have: id (e.g. "dg_" + 5 random chars), title, style, content,`,
  `status:"kept", engine, model:null, createdAt (ISO-8601).`,
  `Write the file as UTF-8 with your native file tool — never via shell redirection.`,
  `Do not modify any existing entry. Do not write anything else. Exit when done.`,
].join('\n')

function buildPrompt(style: DiagramStyle, instruction: string): string {
  return [
    `Read the file at: {{FILE}}`,
    `Read the existing sidecar (if any) at: {{SIDECAR}}`,
    ``,
    instruction,
    APPEND_CONTRACT,
  ].join('\n')
}

export const DIAGRAM_PRESETS: DiagramPreset[] = [
  {
    name: '',
    label: 'Flowchart',
    hint: 'default · Mermaid flowchart',
    style: 'mermaid',
    group: 'anywhere',
    prompt: buildPrompt(
      'mermaid',
      `Produce a Mermaid flowchart (\`flowchart LR\` or \`TD\`) that explains how this content's\n` +
        `components or steps connect. Use the file's own nouns as node labels. Keep it under ~14 nodes.\n` +
        `Set "style":"mermaid" and put the Mermaid source in "content".`,
    ),
  },
  {
    name: 'sequence',
    label: 'Sequence',
    hint: 'Mermaid sequence diagram',
    style: 'mermaid',
    group: 'anywhere',
    prompt: buildPrompt(
      'mermaid',
      `Produce a Mermaid \`sequenceDiagram\` showing the ordered interactions / messages between\n` +
        `the actors or systems described. Set "style":"mermaid".`,
    ),
  },
  {
    name: 'mindmap',
    label: 'Mindmap',
    hint: 'Mermaid mindmap',
    style: 'mermaid',
    group: 'anywhere',
    prompt: buildPrompt(
      'mermaid',
      `Produce a Mermaid \`mindmap\` that organises the document's topics hierarchically from a\n` +
        `single root. Set "style":"mermaid".`,
    ),
  },
  {
    name: 'architecture',
    label: 'Architecture',
    hint: 'Mermaid layered/graph view',
    style: 'mermaid',
    group: 'anywhere',
    prompt: buildPrompt(
      'mermaid',
      `Produce a Mermaid \`flowchart\` grouped with \`subgraph\` blocks to show the system's layers /\n` +
        `boundaries and the data flow between them. Set "style":"mermaid".`,
    ),
  },
  {
    name: 'boxes',
    label: 'Boxes',
    hint: 'plain ASCII boxes',
    style: 'ascii',
    group: 'anywhere',
    prompt: buildPrompt(
      'ascii',
      `Produce a compact ASCII box-and-arrow diagram (use +, -, |, and --> ) that a developer can\n` +
        `paste into any plaintext context. Set "style":"ascii" and put the raw text in "content".`,
    ),
  },
  {
    name: 'uml',
    label: 'UML',
    hint: 'PlantUML source',
    style: 'plantuml',
    group: 'engine',
    unavailable: 'PlantUML render engine not bundled yet — source is shown as text',
    prompt: buildPrompt(
      'plantuml',
      `Produce a PlantUML class or component diagram (@startuml … @enduml). Set "style":"plantuml".`,
    ),
  },
]

export const DIAGRAM_PRESETS_BY_GROUP = {
  anywhere: DIAGRAM_PRESETS.filter((p) => p.group === 'anywhere'),
  engine: DIAGRAM_PRESETS.filter((p) => p.group === 'engine'),
}
