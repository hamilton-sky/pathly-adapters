"""In-memory cross-feature file-claim registry — gates concurrent feature builds.

A feature's build claims the set of files/dir-globs its tasks will touch. A second
feature whose claim OVERLAPS an active claim is refused (serialized); a DISJOINT claim
runs in parallel. A feature that declared no files claims the WILDCARD, which overlaps
everything — so un-annotated features serialize conservatively. Purely in-process
(mirrors board_lock); the pre-isolation safety net until worktree-per-feature isolation
(parallel-fleet) lands. Cleared on server restart.
"""

from __future__ import annotations

import threading

# scope (feature) -> set of file/dir tokens it is actively claiming.
_claims: dict[str, set[str]] = {}
_lock = threading.Lock()

# A feature that declared NO files claims this → overlaps every other claim.
WILDCARD = "*"


def _norm(files) -> set[str]:
    """Normalize a file list to a token set; empty → {WILDCARD}."""
    out = {
        str(f).strip().replace("\\", "/").rstrip("/")
        for f in (files or [])
        if str(f).strip()
    }
    return out or {WILDCARD}


def _pair_overlap(a: str, b: str) -> bool:
    if a == WILDCARD or b == WILDCARD or a == b:
        return True
    # directory containment: "src/api" claims cover "src/api/routes.py"
    return a.startswith(b + "/") or b.startswith(a + "/")


def overlaps(a, b) -> bool:
    """True if any token in claim `a` touches any token in claim `b`."""
    sa, sb = _norm(a), _norm(b)
    return any(_pair_overlap(x, y) for x in sa for y in sb)


def try_claim(scope: str, files) -> str | None:
    """Register `scope`'s claim iff it does not overlap another active feature's.

    Returns None on success (claim registered), or the name of the FIRST overlapping
    active feature on conflict (nothing registered). Atomic. Re-claiming the same
    scope refreshes its file set.
    """
    want = _norm(files)
    with _lock:
        for other, ofiles in _claims.items():
            if other == scope:
                continue
            if any(_pair_overlap(x, y) for x in want for y in ofiles):
                return other
        _claims[scope] = want
        return None


def release(scope: str) -> None:
    """Drop `scope`'s claim (idempotent)."""
    with _lock:
        _claims.pop(scope, None)


def active(exclude_scope: str | None = None) -> dict[str, list[str]]:
    """Snapshot of current claims as {scope: [files]}, optionally excluding one scope."""
    with _lock:
        return {s: sorted(fs) for s, fs in _claims.items() if s != exclude_scope}
