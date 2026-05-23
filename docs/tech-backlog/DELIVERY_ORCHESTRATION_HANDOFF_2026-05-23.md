# Delivery Orchestration Handoff — 2026-05-23

## Context

The previous agent implemented the first scaffold for the Phase 0 Delivery Foundation:

- LangGraph Supervisor: `careerloop/session/supervisor_graph.py`
- Transport abstraction: `careerloop/transport/base.py`, `terminal_chat.py`, `telegram.py`
- Persistence: `careerloop/memory/checkpointer.py`, `supabase_schema.sql`
- Assisted apply concept: `careerloop/execution/kimi_bridge.py`
- CLI/chat entry files: `careerloop/chat_cli.py`, `careerloop/llm_chat.py`

Treat this as directionally correct but not production-ready.

## Product Decision

CareerLoop is moving from a CLI-only backend to a transport-agnostic conversational product. The canonical path is:

```text
CLI / Telegram / WhatsApp / UI
→ TransportAdapter parses payload into UserEvent
→ UserEvent maps into ConversationState
→ LangGraph Supervisor routes state
→ focused subgraph/tool runs
→ AgentAction/message returns through TransportAdapter
```

The Supervisor is the orchestration boundary. Transport code must not own business logic.

## Safety Decision

The Kimi/Hermes bridge is allowed only as assisted execution:

```text
Application pack generated
→ user reviews pack
→ user explicitly approves one job
→ bridge fills that job's ATS form
→ final submit occurs only inside that approved job context
→ ledger records the application
```

Do not implement unattended queue processing, autonomous job selection, or bulk auto-submit. This is locked in Tracker decisions A7 and A13.

## Known Gaps

1. `TransportAdapter.receive()` currently invokes the graph with a `UserEvent` object, while `supervisor_graph.py` expects a dict-like `ConversationState`. Fix this first.
2. `intent_router()` is placeholder-level. It does not yet route scan, brief, apply, edit, or follow-up commands.
3. `scan_jobs_tool()` and `check_liveness_tool()` call Node scripts through subprocesses but have no timeout, cwd, or structured error envelope.
4. `pack_generating_node()` assumes `council_state` is complete enough for `get_council_graph().invoke()`. Add validation before invoking.
5. `human_approval_node()` uses `interrupt()` but no test proves resume behavior with `PostgresSaver`.
6. `kimi_bridge.py` is mock-only and prints "Clicked Submit Application." Replace this with dry-run/approved-run language before user demos.
7. Supabase `DATABASE_URL` is required for the checkpointer, but no local fallback or integration test exists.

## Next Implementation Order

1. Add a pure mapper: `UserEvent` → `ConversationState`.
2. Add graph unit tests for:
   - `IDLE` + "scan"
   - `IDLE` + "brief"
   - `PACK_GENERATING`
   - `PACK_READY` interrupt
   - rejected approval returns to review state
3. Add subprocess tool timeouts and structured return payloads.
4. Prove `PostgresSaver` interrupt/resume with a real or test database.
5. Wire `TerminalChatAdapter` to the Supervisor and run a local smoke test.
6. Only then continue Telegram/WhatsApp webhook work.
7. Convert `kimi_bridge.py` to:
   - `dry_run(application_pack, job_url)`
   - `execute_approved(application_pack, job_url, approval_token)`
   - ledger write after success

## Docs Updated

- `docs/product/PRD.md`
- `docs/product/TECH_ROADMAP.md`
- `docs/engineering/CANONICAL_ARCHITECTURE.md`
- `docs/tech-backlog/TRACKER.md`
- `docs/README.md`
- `docs/product/README.md`
- `docs/engineering/README.md`
- `docs/tech-backlog/README.md`
- `docs/learnings/README.md`
- `docs/learnings/dev-blog/2026-05-23-delivery-orchestration-scaffold.md`

## Handoff Verdict

Aligned architecture, scaffold implementation, high verification debt. The next agent should harden contracts and tests before adding more features.
