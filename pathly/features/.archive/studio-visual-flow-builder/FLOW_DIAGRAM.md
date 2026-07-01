# studio-visual-flow-builder - Flow Diagram

## Happy Path: visual authoring to export

```
[User selects flow]
        |
        v
[useFlowFile reads YAML]
        |
        v
[flowToGraph converts model]
        |
        v
[React Flow canvas renders nodes/edges]
        |
        +-- drag skill/agent --> [VisualView drop handler]
        |                             |
        |                             v
        |                     [update FlowYaml agent_map/states]
        |
        +-- connect nodes ----> [useFlowGraph onConnect]
        |                             |
        |                             v
        |                     [update FlowYaml transitions]
        |
        +-- click node/edge --> [Inspector panel]
                                      |
                                      v
                              [update rules/actions]
                                      |
                                      v
                              [Validation passes]
                                      |
                                      v
                              [YAML preview/export]
```

## YAML edit fallback

```
[User edits YAML]
        |
        v
[YamlView parse attempt]
        |
        +-- valid ----> [set FlowYaml] ----> [Visual graph rehydrates]
        |
        +-- invalid --> [show parse error]
                         |
                         v
                  [keep last valid graph]
```

## Export flow

```
[User chooses export target]
        |
        v
[Run validation]
        |
        +-- errors --> [disable export and show issues]
        |
        +-- warnings --> [require explicit approval]
        |
        +-- pass ----> [serialize canonical YAML]
                         |
                         v
                [write/copy target files]
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| `useFlowFile` | Reads, parses, saves, and syncs selected flow YAML |
| `flowToGraph` | Converts Pathly YAML flow data into React Flow nodes and edges |
| `VisualView` | Canvas shell, drop target, inspector host, validation/export surface |
| `NodePanel` | Docked node inspector |
| `EdgePanel` | Docked transition inspector |
| `YamlView` | YAML preview and direct edit surface |
| `pathlyApi` | Renderer service bridge to filesystem IPC |
