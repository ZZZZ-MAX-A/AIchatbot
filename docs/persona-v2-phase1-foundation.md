# Persona V2 Phase 1: Observe-only foundation

## Status

Phase 1 is deliberately observe-only. It introduces stable persona/account
scope metadata without changing the production chat route.

The following invariants are mandatory while Phase 1 is deployed:

- Aike continues to load the existing globally active role card.
- Private and group chat keep the existing `session_key(event)` values.
- Message persistence, formal summaries, gap-scene summaries, manual memory,
  MemoryRAG, image cache, sticker state, and TTS candidates keep their current
  storage and lookup behavior.
- Database schema version remains 7 and no persona columns or V2 tables exist.
- `routing_v2_active` and `memory_v2_active` are always `false`, even if an
  operator accidentally enables a request flag early.

## Configuration

The foundation reads these settings:

```env
ENABLE_PERSONA_ROUTING_V2=false
ENABLE_PERSONA_MEMORY_V2=false
PERSONA_ROUTING_V2_BOT_IDS=
PERSONA_MEMORY_V2_BOT_IDS=
LEGACY_PERSONA_ID=aike
LEGACY_ROLE_CARD_KEY=aike
BOT_PERSONA_BINDINGS=
```

`BOT_PERSONA_BINDINGS` uses semicolon-separated entries:

```text
bot_self_id=persona_id:role_card_key
```

Persona IDs are permanent lowercase identifiers. Invalid or duplicate
bindings are omitted and reported in the runtime artifact instead of being
used for routing.

The two feature gates and their per-bot allowlists are intentionally separate.
An empty allowlist means no account requests V2. In Phase 1 a request can be
observed, but it cannot activate V2 routing or memory.

## Runtime observation

RootGraph chat observations and AI error log records include:

- `bot_self_id`
- `persona_id`
- `runtime_mode`
- whether V2 routing or memory was requested
- whether the legacy session key was preserved
- a fail-closed configuration error code when applicable

The artifact is diagnostic metadata only. It is not passed into role-card
loading, memory retrieval, persistence, summarization, or RAG search.

## Rollback

No database rollback is required for Phase 1.

Operational rollback:

1. Set both Persona V2 feature gates to `false`.
2. Clear both per-bot allowlists.
3. Restart only the QQ bot process.

Code rollback can remove `persona_scope.py` and its runtime artifact/log
integration without migrating or repairing any stored chat data. Existing
messages, summaries, long-term memory, and embeddings remain untouched.

## Gate for Phase 2

Do not activate account-bound role routing until all of the following are
available:

- the second QQ bot `self_id`;
- a stable new `persona_id`;
- the new role-card key/content;
- an independently logged-in NapCat connection and port plan;
- simultaneous two-account routing tests;
- proof that replies are sent by the bot instance that received the event;
- an explicit decision on whether the second account starts without TTS and
  persistent memory (recommended).

Phase 2 should route only the second account. Aike remains on the legacy path
until the new account has passed isolation, ordering, failure, and rollback
tests.
