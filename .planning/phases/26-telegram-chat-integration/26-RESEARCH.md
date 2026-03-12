# Phase 26: Telegram Chat Integration - Research

**Researched:** 2026-03-09
**Domain:** Telegram Bot API, chat message ingestion, webhook integration
**Confidence:** HIGH

## Summary

Telegram Chat Integration adds Telegram as a second chat source alongside Slack. The project already has a mature integration pattern (Slack, GitHub, Notion, Fathom) with shared OAuth/token utilities, a Provider enum, WorkspaceIntegration model, sync cursors, embedding pipeline, and linking engine. Telegram differs from Slack in one key way: it uses Bot API tokens (not OAuth) -- there is no OAuth flow. The bot token is entered directly (like Fathom's API key pattern), and webhooks use a `secret_token` header for verification instead of HMAC-SHA256 signing.

The Telegram Bot API is simple and stable. The project does NOT need a Telegram library (python-telegram-bot, aiogram, etc.) -- the existing `httpx.AsyncClient` pattern used for Slack/Linear token exchange is sufficient for the handful of API calls needed (setWebhook, getChat, getMe). Message ingestion happens via webhooks (Telegram POSTs updates to our endpoint), matching the existing Slack Events API pattern exactly.

**Primary recommendation:** Use the raw Telegram Bot API with httpx (no library), mirror the Slack integration architecture (router + services + model + migration), use the Fathom-style API key input for bot token entry, and store the bot token in Vault.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | (existing) | Telegram Bot API calls | Already in project for Slack/Linear/GitHub API calls |
| FastAPI | (existing) | Webhook endpoint | Existing framework, same pattern as Slack events endpoint |
| SQLModel | (existing) | TelegramMessage model | Same pattern as SlackMessage model |
| Supabase Vault | (existing) | Bot token storage | Same pattern as Slack bot token storage |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hmac (stdlib) | - | Secret token comparison | Webhook verification (compare_digest) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw httpx | python-telegram-bot | PTB adds ~2MB dependency for 3 API calls; project already uses httpx everywhere |
| Raw httpx | aiogram | Same reasoning -- heavyweight async framework for simple webhook receipt |

**Installation:**
```bash
# No new dependencies needed -- httpx and FastAPI already in project
```

## Architecture Patterns

### Recommended Project Structure
```
backend/src/
├── models/
│   └── telegram.py           # TelegramMessage SQLModel
├── routers/
│   └── telegram.py           # /api/telegram/* endpoints
├── services/
│   ├── telegram_bot.py       # Bot token management, setWebhook, getMe
│   └── telegram_events.py    # Webhook update processing, message filtering
supabase/migrations/
└── 00019_telegram_messages.sql  # Table, indexes, RLS, provider constraint updates
apps/web/src/
├── components/icons/
│   └── brand-logos.tsx        # Add TelegramLogo SVG
├── components/onboarding/
│   └── step-sources.tsx       # Add Telegram card to sources grid
└── lib/
    └── api.ts                 # Add connectTelegram, disconnectTelegram functions
```

### Pattern 1: Webhook Endpoint (mirror Slack events)
**What:** POST /api/telegram/webhook receives Telegram updates, verifies secret_token header, dispatches to background processing
**When to use:** All incoming Telegram messages
**Example:**
```python
# Source: Telegram Bot API docs + existing Slack events pattern
@router.post("/webhook")
async def receive_telegram_updates(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    # Verify secret token header (Telegram's equivalent of Slack HMAC)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    settings = config_module.get_settings()
    if not hmac.compare_digest(secret, settings.TELEGRAM_WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Invalid secret token")

    payload = await request.json()
    # Look up workspace by bot token association
    # Dispatch to background task for fast 200 response
    background_tasks.add_task(_process_update_background, payload, workspace_id)
    return {"status": "ok"}
```

### Pattern 2: Bot Token Entry (mirror Fathom API key)
**What:** User enters Telegram bot token in a form (not OAuth), token stored in Vault, setWebhook called to register our endpoint
**When to use:** Telegram connection flow
**Example:**
```python
# Source: existing Fathom connect pattern + Telegram Bot API
async def connect_telegram_bot(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    bot_token: str,
    settings: Settings,
) -> dict:
    # 1. Validate token by calling getMe
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
    data = resp.json()
    if not data.get("ok"):
        raise TelegramError("Invalid bot token")

    bot_info = data["result"]

    # 2. Store token in Vault
    vault_name = token_name(Provider.TELEGRAM, workspace_id, "bot_token")
    await store_token(session, vault_name, bot_token)

    # 3. Set webhook with secret_token
    webhook_url = f"{settings.BACKEND_URL}/api/telegram/webhook"
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": webhook_url, "secret_token": secret, "allowed_updates": ["message", "edited_message"]},
        )

    # 4. Upsert integration records
    await upsert_oauth_token(session, workspace_id, user_id, Provider.TELEGRAM, access_token_name=vault_name)
    await upsert_workspace_integration(session, workspace_id, Provider.TELEGRAM, external_id=str(bot_info["id"]),
        config={"bot_username": bot_info.get("username"), "external_name": f"@{bot_info.get('username', '')}"})

    await session.commit()
    return bot_info
```

### Pattern 3: Message Model (mirror SlackMessage)
**What:** TelegramMessage table with workspace scoping, upsert support, thread tracking
**When to use:** All message storage
**Example:**
```python
class TelegramMessage(SQLModel, table=True):
    __tablename__ = "telegram_messages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "chat_id", "message_id", name="uq_tg_msg"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    message_id: int = Field(nullable=False)              # Telegram message ID (int, unique within chat)
    chat_id: int = Field(nullable=False)                  # Telegram chat ID (negative for groups)
    chat_title: str | None = Field(default=None)          # Group/channel name
    chat_type: str | None = Field(default=None)           # "group", "supergroup", "channel", "private"
    from_user_id: int | None = Field(default=None)        # Telegram user ID
    from_username: str | None = Field(default=None)       # @username at ingestion time
    from_first_name: str | None = Field(default=None)     # First name at ingestion time
    text: str = Field(nullable=False)
    reply_to_message_id: int | None = Field(default=None) # Thread equivalent
    is_reply: bool = Field(default=False)
    telegram_date: datetime | None = Field(default=None)  # Unix timestamp from Telegram
    raw_data: dict = Field(default_factory=dict, sa_column=Column(JSONB, ...))
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime | None = Field(default=None, ...)
```

### Anti-Patterns to Avoid
- **Installing python-telegram-bot or aiogram:** Overkill for webhook-only ingestion. The project only needs to receive updates and make 3 API calls (getMe, setWebhook, deleteWebhook). httpx handles this.
- **Using polling (getUpdates):** The project runs a web server -- webhooks are the correct approach, matching Slack Events API pattern.
- **Storing bot token in plain text:** Must use Vault, same as Slack bot token.
- **Skipping secret_token verification:** Telegram supports secret_token header -- always verify it. This replaces Slack's HMAC-SHA256 but is simpler (just string comparison).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token storage | Custom encryption | Supabase Vault (`store_token`/`read_token`) | Existing pattern, encrypted at rest |
| Integration status | Custom status tracking | `WorkspaceIntegration` + `Provider` enum | Existing shared model, already powers /api/integrations/status |
| OAuth state signing | N/A | Not needed -- Telegram uses direct token entry | No OAuth flow for Telegram bots |
| Message-to-ticket linking | Custom text search | Existing `linking.py` engine | Already searches by `ilike(%identifier%)` -- just add telegram_message source type |
| Embedding generation | Custom pipeline | Existing `embedding.queue_embedding_generation()` | Same pipeline as Slack messages |

**Key insight:** 90% of the Telegram integration code follows existing patterns. The Slack integration is the blueprint -- swap HMAC verification for secret_token header check, swap OAuth for direct token entry, and the rest is identical.

## Common Pitfalls

### Pitfall 1: Multi-Workspace Bot Token Conflicts
**What goes wrong:** A single Telegram bot can only have one webhook URL. If two workspaces connect the same bot, the second workspace's setWebhook call overwrites the first.
**Why it happens:** Telegram's webhook is per-bot, not per-endpoint-path.
**How to avoid:** Include workspace_id in the webhook URL path: `/api/telegram/webhook/{workspace_id}`. This way each workspace gets a unique URL, and even though setWebhook overwrites, each workspace uses its own bot.
**Warning signs:** Messages stop arriving for one workspace when another connects.

### Pitfall 2: Telegram Chat IDs are 64-bit Integers
**What goes wrong:** Telegram chat_id and user_id can exceed JavaScript's Number.MAX_SAFE_INTEGER (2^53). They can also be negative (groups/channels).
**Why it happens:** Telegram uses 64-bit integer IDs, group chat IDs are negative.
**How to avoid:** Use BIGINT in PostgreSQL (not INTEGER). In the SQLModel, use Python `int` which handles arbitrary precision. On the frontend, treat IDs as strings if displayed.
**Warning signs:** Truncated or wrong chat IDs, especially for large groups.

### Pitfall 3: Missing Webhook Re-registration on URL Change
**What goes wrong:** If the backend URL changes (e.g., ngrok restart, deployment URL change), the webhook stops working because Telegram still points to the old URL.
**How to avoid:** Re-register webhook on connect/reconnect. Consider a startup task that re-registers all active Telegram webhooks. Store webhook URL in integration config for comparison.
**Warning signs:** Messages stop arriving after deployment.

### Pitfall 4: Channel Posts vs Group Messages
**What goes wrong:** Channel posts (broadcast channels) have no `from` field -- the sender is `sender_chat`. Group messages have `from` with user info.
**Why it happens:** Telegram has four chat types with different field availability.
**How to avoid:** Handle both `from` and `sender_chat` fields. For channels, use the channel title as the "sender".
**Warning signs:** NullPointerError on `from.id` for channel messages.

### Pitfall 5: Provider Enum and DB Constraints
**What goes wrong:** Adding `TELEGRAM` to the Python Provider enum but forgetting to update the CHECK constraints on `oauth_tokens`, `workspace_integrations`, `webhook_deliveries`, and `sync_cursors` tables.
**Why it happens:** Multiple tables have `CHECK (provider IN ('linear', 'slack', ...))` constraints.
**How to avoid:** Migration must ALTER all CHECK constraints to include 'telegram'. Also update the embeddings `source_type` CHECK to include 'telegram_message'.
**Warning signs:** Insert fails with constraint violation.

### Pitfall 6: Bot Must Be Added to Group
**What goes wrong:** User connects bot token but forgets to add the bot to their Telegram group. No messages arrive.
**Why it happens:** Telegram bots can only see messages in groups they're a member of, and they need "Group Privacy" turned off in BotFather settings to see all messages (not just commands).
**How to avoid:** Document in the UI that the bot must be added to groups. Consider calling getChat to verify group access. Show a "setup instructions" section after connecting.
**Warning signs:** Bot connects successfully but no messages are ingested.

## Code Examples

### Telegram Webhook Verification
```python
# Source: Telegram Bot API docs (https://core.telegram.org/bots/api#setwebhook)
import hmac

def verify_telegram_secret(request_header: str, expected_secret: str) -> bool:
    """Verify Telegram webhook secret token.

    Unlike Slack's HMAC-SHA256, Telegram uses a simple secret token
    sent in the X-Telegram-Bot-Api-Secret-Token header.
    """
    return hmac.compare_digest(request_header, expected_secret)
```

### Telegram API Call Pattern
```python
# Source: Telegram Bot API docs
TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"

async def telegram_api_call(bot_token: str, method: str, **params) -> dict:
    """Make a Telegram Bot API call using httpx."""
    url = f"{TELEGRAM_API_BASE.format(token=bot_token)}/{method}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=params)
    data = resp.json()
    if not data.get("ok"):
        raise TelegramError(f"API error: {data.get('description', 'unknown')}")
    return data["result"]
```

### Message Filtering (mirror Slack pattern)
```python
# Source: existing slack_events.py pattern
def _should_filter_telegram(update: dict) -> bool:
    """Filter out non-relevant Telegram messages."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return True

    # Skip non-text messages (photos, stickers, etc.)
    if "text" not in message:
        return True

    # Skip bot messages
    from_user = message.get("from", {})
    if from_user.get("is_bot", False):
        return True

    # Skip short messages (< 10 chars, matching Slack filter)
    if len(message.get("text", "")) < 10:
        return True

    return False
```

### Integration in Linking Engine
```python
# Source: existing linking.py pattern
# Add to _SOURCE_SUMMARY_MAP:
"telegram_message": (
    TelegramMessage,
    lambda r: (
        f"Telegram by {r.from_first_name or r.from_username or 'Unknown'} in {r.chat_title or 'DM'}",
        r.text[:200],
    ),
),

# Add to SOURCE_TYPE_MAP:
"telegram": ["telegram_message"],
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Polling (getUpdates) | Webhooks with secret_token | Bot API 6.0+ (2022) | Webhook + secret_token is now standard |
| HMAC verification | secret_token header | Bot API 6.0 | Simpler than Slack's HMAC -- just header comparison |
| python-telegram-bot sync | async-first (PTB v21+, aiogram v3+) | 2024-2025 | Libraries went async-only, but raw httpx is simpler for ingestion-only use |

**Deprecated/outdated:**
- Bot API polling for production: Use webhooks
- Unsigned webhooks: Always use secret_token parameter

## Config Settings Required

```python
# Add to Settings class in config.py:
# Telegram Chat Integration
TELEGRAM_WEBHOOK_SECRET: str = ""  # Secret for webhook verification (generate random string)
# Note: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID already exist in config.py
# for Sentry alerts. The chat integration uses per-workspace bot tokens
# stored in Vault, NOT the global TELEGRAM_BOT_TOKEN.
```

**Important distinction:** The existing `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in config.py are for Sentry error alerts (a global admin bot). The chat integration uses per-workspace bot tokens stored in Vault, following the same pattern as Slack bot tokens. These are completely separate.

## Integration Touchpoints

Files that need modification (not new files):

| File | Change | Reason |
|------|--------|--------|
| `backend/src/models/integration.py` | Add `TELEGRAM = "telegram"` to Provider enum | New provider registration |
| `backend/src/routers/integrations.py` | Add `Provider.TELEGRAM` to PROVIDERS list, add config extraction | Integration status endpoint |
| `backend/src/main.py` | Import and include telegram_router | Router registration |
| `backend/src/config.py` | Add `TELEGRAM_WEBHOOK_SECRET` setting | Webhook verification config |
| `backend/src/services/linking.py` | Add telegram_message to `_SOURCE_SUMMARY_MAP` and `SOURCE_TYPE_MAP` | Message-to-ticket linking |
| `apps/web/src/lib/api.ts` | Add `telegram` to `IntegrationStatusResponse`, add `connectTelegram`/`disconnectTelegram` | API client |
| `apps/web/src/components/icons/brand-logos.tsx` | Add `TelegramLogo` SVG component | Brand icon |
| `apps/web/src/components/onboarding/step-sources.tsx` | Add Telegram SourceCard | Onboarding wizard |
| `apps/web/src/app/dashboard/settings/page.tsx` | Add Telegram IntegrationCard | Settings page |
| Multiple migration CHECK constraints | Add 'telegram' to provider checks | DB constraint updates |
| Embeddings source_type CHECK | Add 'telegram_message' | Embedding pipeline |

## Open Questions

1. **Group Privacy Mode**
   - What we know: By default, bots in groups only receive commands (messages starting with /). BotFather has a "Group Privacy" setting that must be turned OFF for the bot to see all messages.
   - What's unclear: Should we detect this and warn the user, or just document it?
   - Recommendation: Show setup instructions in the connect UI explaining: "1) Create a bot via @BotFather, 2) Disable Group Privacy, 3) Add bot to your groups, 4) Enter the token here"

2. **Webhook URL Uniqueness**
   - What we know: Each bot can only have one webhook URL. Including workspace_id in the path solves multi-workspace scenarios.
   - What's unclear: Whether we should use `/api/telegram/webhook/{workspace_id}` (path param) or `/api/telegram/webhook?ws={workspace_id}` (query param)
   - Recommendation: Use path parameter -- it's cleaner and matches the webhook URL registered with Telegram.

3. **Historical Message Backfill**
   - What we know: Telegram Bot API does not support fetching message history. Bots only receive new messages after being added.
   - What's unclear: Should we document this limitation clearly?
   - Recommendation: Show a note in the UI: "Messages will be ingested from the moment the bot is added to a group. Historical messages cannot be retrieved."

## Sources

### Primary (HIGH confidence)
- [Telegram Bot API official docs](https://core.telegram.org/bots/api) - setWebhook, Update/Message/Chat objects, secret_token
- Existing codebase: `backend/src/routers/slack.py`, `backend/src/services/slack_events.py`, `backend/src/services/slack_oauth.py` - Integration patterns
- Existing codebase: `backend/src/models/slack.py`, `backend/src/models/integration.py` - Data model patterns
- Existing codebase: `backend/src/services/linking.py` - Linking engine integration points
- Existing codebase: `backend/src/config.py` - Existing TELEGRAM_BOT_TOKEN (for Sentry alerts, separate from chat integration)

### Secondary (MEDIUM confidence)
- [python-telegram-bot GitHub](https://github.com/python-telegram-bot/python-telegram-bot) - Confirmed v21.11 supports Bot API 8.3
- [aiogram docs](https://docs.aiogram.dev/) - Confirmed v3.26.0, async-first, but unnecessary for this use case
- [Telegram webhook security guide](https://github.com/b0g3r/fastapi-security-telegram-webhook) - FastAPI + secret_token verification pattern

### Tertiary (LOW confidence)
- None -- all findings verified with official docs or codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies needed, uses existing httpx/FastAPI/SQLModel
- Architecture: HIGH - Direct mirror of Slack integration, all patterns proven in codebase
- Pitfalls: HIGH - Verified against Telegram Bot API docs and codebase constraints
- Linking engine: HIGH - Verified _SOURCE_SUMMARY_MAP and SOURCE_TYPE_MAP extension points

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (Telegram Bot API is stable, rarely breaking changes)
