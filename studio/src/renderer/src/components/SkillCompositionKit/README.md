# Skill Composition Kit

Redesigned Skill Composition panel for Pathly Studio (React + TypeScript). Dark-first, dense,
Geist + Geist Mono, sky-blue accent, token/cost as a first-class citizen. Each component sits
in its own folder with its own CSS module. Drop-in replacement for components/SkillComposition;
it reuses the same server API and project store, wired in ONE file: integration.ts.

## Structure

    index.ts            barrel (exports SkillComposition)
    integration.ts      the only Pathly wiring point (services + store)
    types.ts            view-model types
    data/               fragmentMeta, abilities, systemPrompt (curated stand-in data)
    hooks/              catalog, fragment-toggles, composed-preview, expanded-rows, inspector
    SkillComposition/   root panel (header + body)
    SkillSidebar/       collapsible, swappable skill picker (250px picker or 44px rail)
    SkillList, SkillListItem   grouped skill list + row
    FragmentPanel/      right pane: header, Preview/Config tabs, meta, reset
    CompositionSummary/ token-impact strip (body vs fragments bar)
    ConfigView/         Table / Split layout switcher
    FragmentTable, FragmentSplit   the two Config layouts (rows expand inline)
    PreviewView/        tabbed list + composed prompt + inspect drawer
    FragmentListPanel/  Fragments / Abilities / System tabs (checkbox + eye per row)
    ComposedPromptView, InspectDrawer   composed body + slide-up detail drawer

## Integrate (3 steps)

1. Copy the folder into studio/src/renderer/src/components/.
2. Edit integration.ts: fix its two import paths to your services/skillComposition and
   store/projectStore. It expects fetchSkillComposition, previewComposedSkill,
   saveSkillCompositionOverride, resetSkillComposition, and a useProjectPath() hook.
3. Render the SkillComposition component in your workspace. It styles purely with Pathly CSS
   variables, so it needs only the tokens the app already loads via styles.css (no provider).

## State

  - useSkillCompositionCatalog owns selectedSkill; FragmentPanel is keyed by it so per-skill
    UI resets on switch.
  - useFragmentToggles debounce-saves the override (500ms) and re-seeds only on skill/source
    change; onChanged triggers a catalog refetch.
  - useComposedPreview (350ms) gives the authoritative composed token count.
  - Sidebar collapse lives in the root; useExpandedRows drives Config inline expansion;
    usePreviewInspector owns the Preview tab + drawer (eye opens it, checkbox only toggles).

## Placeholder data

The skills/catalog endpoint returns empty descriptions and no per-fragment token counts, so
data/fragmentMeta.ts (purpose + tokens), data/abilities.ts (Abilities tab) and
data/systemPrompt.ts (System tab base + BODY_TOKENS) carry curated stand-ins. Replace with
real library-table values. ComposedPromptView shows a demo body; feed it useComposedPreview
sections through the app MarkdownRenderer to render the real composed text.
