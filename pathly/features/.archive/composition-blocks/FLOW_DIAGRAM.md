# composition-blocks — Flow Diagram

## Primary Flow: Stage → Block → Fragments → Composed Prompt

```mermaid
flowchart TD
    A([FSM: build_prompt called for current_state]) --> B{Active flow has\ncomposition: key?}

    B -- no --> C[compose_skill\nagent, adapter_caps\n— pre-feature path]
    B -- yes --> D{current_state in\ncomposition: map?}

    D -- no --> C
    D -- yes --> E[Lookup block_name\nfrom composition map]

    E --> F[_load_user_blocks\npathlyUserHome/user-blocks.json]
    F --> G[Merge: user_blocks\noverride core blocks by name]

    G --> H{block_name found\nin merged library?}

    H -- no --> I[log WARNING:\nblock missing at runtime]
    I --> C

    H -- yes --> J[resolve_block\napply _entry_parts + capability gating\nper fragment entry]

    J --> K{Any gated fragments\nadapter lacks cap?}
    K -- yes --> L[Drop gated fragment\nsilently]
    K -- no --> M[Keep fragment]
    L --> N
    M --> N

    N[Ordered fragment list\nresolved] --> O[compose_skill_with_block\nskill_body + join fragments\nwith double newline]

    O --> P([Composed prompt returned\nto FSM agent runner])
    C --> P
```

## Fallback / Validation Flow (load time)

```mermaid
flowchart TD
    A([Flow yaml loaded by state.py]) --> B{composition:\nkey present?}

    B -- no --> C([Validation passes\n— unchanged behavior])
    B -- yes --> D[For each state key\nin composition map]

    D --> E{State declared\nin states: list?}
    E -- no --> F([Hard error:\nundeclared state key])
    E -- yes --> G{Block name non-empty\nstring?}

    G -- no --> H([Hard error:\nempty block name])
    G -- yes --> I{Block name in\nmerged library?}

    I -- no --> J([Hard error:\nunknown block name])
    I -- yes --> K{Block has gated fragments?\nDoes resolved adapter\nlack the cap?}

    K -- yes --> L([Warning emitted:\ncapability mismatch\nFlow still allowed to start])
    K -- no --> M([Validation passes\nfor this state binding])

    L --> N([All states checked\nFlow loads])
    M --> N
```

## Author + Store Flow (Studio, Conv 3)

```mermaid
flowchart TD
    A([User opens BlockAuthorForm\nin Studio]) --> B[User enters block name\n+ selects fragments\nfrom 5-item list]

    B --> C{Name non-empty\nand at least\none fragment?}
    C -- no --> D([Validation error shown\nnot saved])
    C -- yes --> E{Name duplicates\na core block?}

    E -- yes --> F[Show warning:\noverrides core block\nallow save]
    E -- no --> G[Write / merge into\npathlyUserHome/user-blocks.json]
    F --> G

    G --> H([User block saved])

    H --> I([User opens Flow Wizard\nStep 4 block dropdown])
    I --> J[Wizard loads core blocks\nhardcoded + user-blocks.json]

    J --> K{user-blocks.json\nexists and valid?}
    K -- no --> L[console.warn\nShow core blocks only]
    K -- yes --> M[Merge: core + user blocks\nin dropdown options]

    L --> N
    M --> N

    N[User selects block\nper state in dropdown] --> O[blockMap state updated\nautosaved to draft]
    O --> P([User clicks Finish\ngenerateYaml emits\ncomposition: map in yaml])
```

## Component Legend

| Node | Meaning |
|---|---|
| `[Name]` | Processing step — a function call or data operation |
| `{Name?}` | Decision point — branches on a boolean condition |
| `([Name])` | Terminal node — final outcome or entry trigger |
| `compose_skill` | Pre-feature composition path (unchanged) |
| `resolve_block` | New function in compose.py; applies capability gating |
| `compose_skill_with_block` | New function in compose.py; assembles skill + block fragments |
| `_load_user_blocks` | Private helper; returns `{}` on any file/parse error |
| `blockMap` | Wizard state: `Record<string, string>` — state → block name |
| `generateYaml` | Extended to accept `blockMap`; emits `composition:` key conditionally |
