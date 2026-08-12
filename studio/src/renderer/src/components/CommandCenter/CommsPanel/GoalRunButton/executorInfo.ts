// One source of truth for what each goal executor dispatches — mirrors the backend:
// supervisor/goal_executor.py (single → drain-dag; team → team-build flow),
// supervisor/scheduler.py (loop → execute-task, role stamped "builder"), and
// core/flows/team-build.flow.yaml (BUILDING→REVIEWING→TESTING→RETRO stages).
// Consumed by the inline hint under the Run controls, the preview modal's Agent/Skill
// rows, and useGoalRunPreview (which loads the skill body).
export interface ExecutorInfo {
  /** Pathly role/agent the run acts as (human-readable). */
  agent: string
  /** Display label of the skill or flow the run sends. */
  skill: string
  /** core/skills-relative path whose body seeds the prompt preview ('' when there is no single skill). */
  skillRel: string
}

const EXECUTOR_INFO: Record<string, ExecutorInfo> = {
  single: { agent: 'single agent', skill: 'development/drain-dag', skillRel: 'development/drain-dag' },
  loop: { agent: 'builder', skill: 'development/execute-task', skillRel: 'development/execute-task' },
  team: { agent: 'builder → reviewer → tester', skill: 'team-build flow', skillRel: '' },
}

/** Executor metadata, defaulting to the `single` shape for any unknown value. */
export function executorInfo(executor: string): ExecutorInfo {
  return EXECUTOR_INFO[executor] ?? EXECUTOR_INFO.single
}
