# Goal Card Visibility Assessment

## Issue
The canonical goal card and its DAG tasks exist on the `pathly-entity-model` feature board, but they can disappear from Studio's Goals view after enough newer board traffic accumulates.

## Verified Behavior
- `GET /comms?feature=pathly-entity-model&scope=pathly-entity-model&type=goal` returns the canonical goal `3434d44d-7ff1-4949-bb60-f680a74e06ea`.
- `GET /comms/tasks?feature=pathly-entity-model` returns the 13 DAG task rows stamped with that `goal_id`.
- `GET /comms?feature=pathly-entity-model&board=feature&scope=pathly-entity-model` returns only the newest 50 messages by default, and that window is currently filled mostly with newer status traffic.
- Studio's Goals view groups only the `messages` array it receives from the generic board loader; it does not fetch goals/tasks separately.

## Root Cause
This is a feed-window problem, not missing board data. The backend `/comms` endpoint defaults to `limit=50`, and Studio's `fetchBoard()` helper was not overriding that limit. Once more than 50 newer messages exist on the board, older `goal` and `task` rows fall out of the payload, so the Goals view has nothing to render even though the goal DAG still exists in the database.

## Fix
Studio's generic board loader now requests `limit=500` in `studio/src/renderer/src/store/commsApi.ts`. That keeps the existing Goals view contract intact while making older goal/task rows much less likely to be pushed out by status chatter.

## Verification
- The live board data still contains the canonical goal and the 13 DAG tasks.
- The patched loader now requests `/comms?...&limit=500`, so the same feature board can include both recent status messages and the older goal/task rows in one payload.
- I did not change the goal/task grouping logic; once those rows are present in `messages`, the existing Goals view will render them.
