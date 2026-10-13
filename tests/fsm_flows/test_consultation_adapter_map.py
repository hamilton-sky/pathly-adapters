"""Phase 0 hygiene fix — consultation.flow.yaml had an adapter_map (PO discussion +
design routed to codex); its siblings feature-consultation.flow.yaml and
project-consultation.flow.yaml had none, despite each declaring in its own header
comment that it is "consultation.flow.yaml lifted one altitude up" (same stages,
same PO/architect/researcher/designer/planner shape, only the terminal artifact
type differs). Reconciled: all three now carry the same per-stage adapter routing.

Also asserts every shipped flow still passes the FSM validator end to end.
"""

from __future__ import annotations

from pathlib import Path

import pathly_data
import yaml

from pathly_orchestrator.fsm.state import validate_flow_dict

_FLOWS_DIR = Path(pathly_data.__file__).parent / "core" / "flows"

_CONSULTATION_SHAPED = [
    "consultation.flow.yaml",
    "feature-consultation.flow.yaml",
    "project-consultation.flow.yaml",
]

_EXPECTED_ADAPTER_MAP = {
    "default": "claude",
    "PO_DISCUSSING": "codex",
    "DESIGNING": "codex",
}


def _load(name: str) -> dict:
    return yaml.safe_load((_FLOWS_DIR / name).read_text(encoding="utf-8"))


def test_consultation_shaped_flows_share_the_same_adapter_map():
    for name in _CONSULTATION_SHAPED:
        flow = _load(name)
        assert flow.get("adapter_map") == _EXPECTED_ADAPTER_MAP, name


def test_all_shipped_flows_pass_validator():
    for path in sorted(_FLOWS_DIR.glob("*.flow.yaml")):
        flow = yaml.safe_load(path.read_text(encoding="utf-8"))
        errors, _warnings = validate_flow_dict(flow)
        assert errors == [], f"{path.name}: {errors}"
