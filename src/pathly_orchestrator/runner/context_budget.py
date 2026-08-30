"""Per-tier character budget for the board-context Context channel.

A single shared budget let whichever tier rendered FIRST (feature — the insertion
order of ``enabled_boards``) spend the whole allowance, so the project/global
entries were always the first to be dropped. They are also the expensive ones: a
cross-cutting decision is far harder for an agent to re-derive than a note from
the feature board it is already sitting on.

This module splits the SAME total across the enabled tiers by weight, then pools
whatever each tier leaves unspent so a quiet tier's surplus still funds a long
entry elsewhere. Total rendered size is unchanged — only the distribution is.
"""

from __future__ import annotations

# Caps the rendered Context body so a long board can't bloat the prompt.
CONTEXT_CHAR_BUDGET = 2000

# Share of CONTEXT_CHAR_BUDGET each tier may spend, mirroring the k-ladder
# (3/2/1) and the per-tier distance gates: attention narrows as the board gets
# further from the task. Normalised over the tiers actually ENABLED for the run,
# so a disabled tier's share is redistributed rather than lost — a feature-only
# run still renders against the full budget, exactly as before.
CONTEXT_BUDGET_WEIGHTS = {"feature": 0.5, "project": 0.3, "global": 0.2}


def allocate_budget(
    tiers: list[str], total: int = CONTEXT_CHAR_BUDGET
) -> dict[str, int]:
    """Split *total* chars across *tiers*, weighted by CONTEXT_BUDGET_WEIGHTS."""
    if not tiers:
        return {}
    weights = {t: CONTEXT_BUDGET_WEIGHTS.get(t, 0.0) for t in tiers}
    denom = sum(weights.values())
    if denom <= 0:  # unknown tier names only — fall back to an even split
        share = total // len(tiers)
        return {t: share for t in tiers}
    return {t: int(total * w / denom) for t, w in weights.items()}


def select_within_budget(
    entries: list[tuple[str, str]],
    tiers: list[str],
    total: int = CONTEXT_CHAR_BUDGET,
) -> list[int]:
    """Return the indices of *entries* that fit, in render order.

    *entries* is ``(tier, rendered_line)``. Each line is charged to its OWN
    tier's budget first, so a chatty feature board can no longer starve the
    project/global channels. A second pass pools the unspent remainder so a
    surplus is not wasted on a board where one tier is quiet.

    At least one entry is always kept — mirroring the previous ``shown > 0``
    guarantee — even when that entry alone exceeds the whole budget.
    """
    budgets = allocate_budget(tiers, total)
    keep: set[int] = set()

    for idx, (tier, line) in enumerate(entries):
        cost = len(line)
        if cost <= budgets.get(tier, 0):
            budgets[tier] -= cost
            keep.add(idx)

    pooled = sum(budgets.values())
    for idx, (_tier, line) in enumerate(entries):
        if idx in keep:
            continue
        if len(line) <= pooled or not keep:
            pooled -= len(line)
            keep.add(idx)

    return sorted(keep)
