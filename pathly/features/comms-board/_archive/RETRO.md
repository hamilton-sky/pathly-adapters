# Comms Board — Backend RETRO

## What shipped
- Phase 1 (Convs 1–3): DB schema, embeddings, HTTP API (8 routes), SSE, FSM injection, board_scope control
- Phase 1.4 (Conv 4): superseded_by suppression, write-time curation (_EMBED_TYPES), labeled governance/semantic channels, dead promotion code removed
- Phase 1.5 (Conv 5): hybrid BM25+semantic search (FTS5 + cosine RRF), mode param on /comms/search, role-based write permissions
- Conv 5 review fixes: project-level override enforcement in comms_post (B1), FTS OperationalError guard (M1), hybrid recency fallback (N1)

## What is NOT shipped (explicitly deferred)
- Phase 14 DAG tasks — next feature: comms-board-skills (depends_on column, GET /comms/tasks, POST /comms/tasks/complete + builder skill update)
- Phase 2 Studio UI — pending design consultation (comms-board-studio plan)
- Phase 5 Board-Storm — long-term (board-storm plan)
- Phase 4 Command Center — long-term (comms-board-command-center plan)

## Backend is fully curl-testable
All deliverables work with zero Studio/Electron changes.
Run: python -m pytest tests/ -q -k comms   → 86 passed

## Next step
comms-board-skills: Phase 14 DAG (depends_on + GET /comms/tasks + POST /comms/tasks/complete) + builder skill update to poll ready tasks.
Do NOT start comms-board-studio until design is confirmed.

## BACKEND_COMPLETE
Signal: BACKEND_COMPLETE
Date: 2026-06-14
