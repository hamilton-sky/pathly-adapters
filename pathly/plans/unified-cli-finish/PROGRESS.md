# PROGRESS — unified-cli-finish

| # | Phase | Status |
|---|---|---|
| 1 | research + architect → comms-post (strip curls) | ✅ DONE (tested) |
| 2 | ~~task-drain fragment~~ → build/drain-dag reclassified board-native (loop too interwoven to extract safely) | ✅ DONE (docs) |
| 3 | evaluate/consolidate/plan → reclassify board-native (docs) | ✅ DONE (docs) |
| 4 | storage-path A: `<feature_path>` in team/* skills (runner-only, safe) | ✅ DONE (snapshots regen) |
| 5 | storage-path B: shared `cli/_discovery.py` dual-scan → status/ff/back/log + db_api._scan_filesystem_features | ✅ DONE (tested) |
| 6 | composition UI: Studio fragment-picker + route | 📝 EXPLAINED IN CHAT (per request; not built) |
| — | adapter sync (`pathly-setup --repair` + `python -m build`) | pending (local install only) |
| — | tests: `test_compose.py` + `test_fsm_ops.py` + `test_cli_discovery.py` | ✅ green (103) |

**Deferred (low priority):** storage-path Category A for `development/*` skills is dual-mode
(installed static + runner) so `<feature_path>` needs interactive-mode handling; utility-skill
discovery prose (reflect/archive/pause/pathly) still says `pathly/plans/*` — cosmetic, agent
finds features either way. Neither blocks new-root features working through the pipeline.
