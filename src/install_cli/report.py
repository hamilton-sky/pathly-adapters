"""Console reporting for what a reconcile removes (dry-run preview and real run).

``--repair`` makes an install declarative — it writes exactly the requested set and
prunes every other Pathly-owned file — so the removals deserve the same visibility as
the writes. Kept apart from ``materialize`` (file sync) and ``orchestrate`` (flow).
"""

from pathlib import Path
from typing import Callable

from .materialize import plan_prunes


def report_would_prune(
    host: str,
    label: str,
    dest: Path,
    files: dict[str, str],
    *,
    repair: bool,
    prune_filter: Callable[[str], bool] | None = None,
) -> None:
    """Dry-run: list the owned files in ``dest`` that fall outside ``files``.

    With ``repair`` they are removed by the real run; without it they are left alone, and
    the note says so (the user sees what ``--repair`` would additionally do).
    """
    names = plan_prunes(files, dest, prune_filter=prune_filter)
    if not names:
        return
    if repair:
        print(f"\n[{host}] Would remove {len(names)} obsolete {label} from {dest}:")
    else:
        print(
            f"\n[{host}] {len(names)} installed {label} in {dest} fall outside the "
            "requested set — kept now, but --repair would remove:"
        )
    for name in names:
        print(f"  {dest / name}")


def report_pruned(host: str, label: str, dest: Path, names: list[str]) -> None:
    """Real run: say what a repair removed instead of pruning silently."""
    if not names:
        return
    print(f"[{host}] Removed {len(names)} obsolete {label} from {dest}:")
    for name in sorted(names):
        print(f"  {dest / name}")
