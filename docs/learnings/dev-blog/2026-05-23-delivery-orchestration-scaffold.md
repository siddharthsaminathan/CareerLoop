# Dev Blog — 2026-05-23: Delivery Orchestration Scaffold

## What Was Done

- Reconciled the May 23 delivery architecture work against the PRD, Tracker, Technology Roadmap, and Canonical Architecture.
- Documented the LangGraph Supervisor as the orchestration boundary for CLI, Telegram, WhatsApp, and future UI transports.
- Recorded first-pass scaffolds for `TransportAdapter`, `UserEvent`, `TerminalChatAdapter`, `supervisor_graph.py`, `PostgresSaver`, and `kimi_bridge.py`.
- Added a next-agent handoff covering implementation gaps and the exact next build order.
- Updated documentation indexes so the handoff and delivery roadmap are discoverable.

## Key Decisions

- Transport code must normalize platform payloads into `UserEvent`, then map into `ConversationState`; it must not own business logic.
- LangGraph Supervisor is the parent orchestration layer. Resume Council stays a focused subgraph/tool path.
- Kimi/Hermes assisted apply is permitted only after explicit per-job user approval. No autonomous queue, no bulk submit, no job selection while the user is absent.
- The current code is a scaffold, not a completed migration. Documentation now reflects implementation truth rather than aspirational completion.

## Issues Encountered

- `TransportAdapter.receive()` currently invokes the graph with a `UserEvent` object, but `supervisor_graph.py` expects dict-like `ConversationState`.
- `intent_router()` exists but is not yet a real router.
- `kimi_bridge.py` currently prints submit-oriented mock output and needs safer dry-run/approved-run semantics.
- `PostgresSaver` exists behind `DATABASE_URL`, but no interrupt/resume verification has been run.

## Files Changed

- `docs/product/PRD.md`
- `docs/product/TECH_ROADMAP.md`
- `docs/engineering/CANONICAL_ARCHITECTURE.md`
- `docs/tech-backlog/TRACKER.md`
- `docs/tech-backlog/DELIVERY_ORCHESTRATION_HANDOFF_2026-05-23.md`
- `docs/README.md`
- `docs/product/README.md`
- `docs/engineering/README.md`
- `docs/tech-backlog/README.md`
- `docs/learnings/README.md`

## Next Session

- Fix `UserEvent` → `ConversationState` mapping and add graph tests before expanding Telegram/WhatsApp.
- Prove one local TerminalChat flow end-to-end.
- Replace `kimi_bridge.py` mock submit language with dry-run and explicit approved execution modes.
