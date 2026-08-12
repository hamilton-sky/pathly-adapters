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
      'Produce a Mermaid flowchart (`flowchart LR` or `TD`) that explains how this content\'s components or steps connect, using the file\'s own nouns as node labels and keeping the diagram under ~14 nodes. Apply these parser-safety rules without exception: (1) Always wrap every node label in double quotes — write `nodeID["label text"]` rather than `nodeID[label text]`; this single rule neutralises parentheses, colons, single-quotes, slashes, pipes, angle brackets, and most other special characters. (2) Never use a Mermaid reserved word as the bare node identifier; the full reserved set is: `graph`, `flowchart`, `subgraph`, `end`, `class`, `click`, `style`, `linkStyle`, `direction` — prefix every one of them, e.g. `n_end["end"]`, `n_style["style"]`, `n_linkStyle["linkStyle"]`, `node_graph["graph"]`. (3) To include a literal double-quote character inside a label, use the HTML entity `&quot;` — write `["say &quot;hello&quot;"]`, never `["say "hello""]`. (4) For edge labels using the pipe syntax, keep the label text free of nested pipe characters, e.g. `-->|"result value"|`. Set "style":"mermaid" and put the Mermaid source in "content".',
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
      'Produce a Mermaid `sequenceDiagram` showing the ordered interactions and messages between the actors or systems described. Follow these parser-safety rules without exception: (1) Never place a semicolon (`;`) anywhere in message text or in a participant alias — it is an unconditional line terminator in the Mermaid sequence lexer and no quoting escapes it; if a label would require a semicolon, reword it to remove the semicolon entirely. (2) Never use HTML entities (`&amp;`, `&lt;`, `&gt;`, `&apos;`, `&quot;`, `&#N;`, etc.) in message text or aliases — every such entity contains a semicolon and will trigger the same termination bug; write the raw character instead (literal `&`, `<`, `>`). (3) Any participant whose identifier clashes with a Mermaid reserved word (`note`, `over`, `loop`, `alt`, `opt`, `par`, `and`, `end`, `activate`, `deactivate`, `participant`, `actor`) must be declared with an alias using `participant reservedWord as SafeAlias` and then referenced only by `SafeAlias` — the name after `as` — in every arrow statement; the bare reserved word must never appear as an arrow source or target. For example: `participant loop as LoopSvc` followed by `LoopSvc->>A: message`, never `loop->>A: message`. Set "style":"mermaid".',
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
      'Produce a Mermaid `mindmap` that organises the document\'s topics hierarchically from a single root node. Obey these parser-safety rules exactly: (1) never use the bare word `mindmap` as a node label — if you must label a node with that word, wrap it in double quotes; (2) never place `{` or `}` anywhere in a node label, quoted or unquoted, as there is no escaping mechanism that makes curly braces safe; (3) never place `(...)` or `[...]` where text continues on the same line after the closing delimiter — the parser treats those closing delimiters as the end of a shape declaration, so any trailing text causes a parse error; text that precedes a `(...)` or `[...]` at the very end of the label line is fine, but text that follows is not; (4) do not rely on double-quote wrapping to neutralise shape delimiters — `"...(parens)..."` and `"...[brackets]..."` fail just as they do unquoted. Set "style":"mermaid".',
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
      'Produce a Mermaid flowchart (`flowchart LR` or `TD`) grouped with `subgraph` blocks to show the system\'s layers / boundaries and the data flow between them. Apply these parser-safety rules without exception: (1) wrap every node label in double quotes — `nodeID["label text"]` — which neutralises parentheses, colons, slashes, pipes, and most special characters; (2) give every subgraph an explicit quoted title via an id — `subgraph s1["Layer name"]` ... `end` — and never write a bare `subgraph Layer name`; (3) never use a Mermaid reserved word (`graph`, `flowchart`, `subgraph`, `end`, `class`, `click`, `style`, `linkStyle`, `direction`) as a bare node or subgraph identifier — prefix it, e.g. `n_end["end"]`; (4) to include a literal double-quote in a label, use the HTML entity `&quot;`. Set "style":"mermaid".',
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

const DIAGRAM_PRESETS_BY_GROUP = {
  anywhere: DIAGRAM_PRESETS.filter((p) => p.group === 'anywhere'),
  engine: DIAGRAM_PRESETS.filter((p) => p.group === 'engine'),
}
