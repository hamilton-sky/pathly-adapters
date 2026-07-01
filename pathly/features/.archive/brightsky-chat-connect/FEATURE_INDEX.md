# Feature Index — brightsky-chat-connect

**Rigor:** lite  
**Status:** PLANNING  
**Pipeline:** STORM → PLAN → BUILD → DONE

## What this feature is

Add Brightsky (the hosted NestJS chat backend) as a selectable backend in Pathly Studio's ChatPanel, alongside the existing local LLM options. Users authenticate via Google OAuth through the Electron `brightsky://` custom protocol, then stream chat responses over a direct renderer WebSocket — no IPC bridge for chat traffic.

## Who benefits

- Studio developers who already use Brightsky as their hosted backend and want one desktop surface instead of two clients.
- Studio users evaluating cloud-hosted chat as an alternative to local models.

## Delivery plan

| Conversation | Scope | Stories |
|---|---|---|
| Conv 1 | Auth layer: IPC handler, Zustand store, preload bridge, global types | S-01, S-02, S-03, S-08 |
| Conv 2 | WebSocket client, ModelSelector UI, ChatPanel wiring, sessions dropdown | S-04, S-05, S-06, S-07, S-09, S-10 |

## Files produced by this feature

**New files:**
- `studio/src/main/ipc/brightsky.ts`
- `studio/src/renderer/src/store/brightskyStore.ts`
- `studio/src/renderer/src/lib/brightskyClient.ts`

**Modified files:**
- `studio/src/main/preload/index.ts`
- `studio/src/main/index.ts`
- `studio/src/renderer/src/types/global.d.ts`
- `studio/src/renderer/src/store/modelStore.ts`
- `studio/src/renderer/src/components/ChatPanel/ModelSelector.tsx`
- `studio/src/renderer/src/components/ChatPanel/index.tsx`

## Out of scope

- Server-side changes to Brightsky NestJS backend
- Local LLM backend changes (Ollama / node-llama-cpp remain unchanged)
- Custom auth providers beyond Google OAuth
- Tool-calling / agent orchestration over Brightsky transport
- File / image attachments
- Offline session caching
- Multi-account switching
- Cross-session search or bulk session management

## Open questions (from PO — not blocking Conv 1)

- Does Brightsky expose a model picker to surface in Studio, or does it auto-route server-side?
- Should Brightsky sessions appear in a unified ConductorHeader list or a separate section?
- Is there a rate limit / quota the UI should display?
- Does the WebSocket need keep-alive pings to survive Render idle timeout?
