# Integration Setup Guide

Step-by-step guide for connecting Linear and Slack to ContextOS.

## Prerequisites

Before setting up integrations, make sure the project is running locally:

```bash
# 1. Start Docker Desktop

# 2. Start Supabase
supabase start

# 3. Start ngrok (required for OAuth callbacks)
ngrok http 8000
# Copy the HTTPS forwarding URL (e.g. https://abc-xyz.ngrok-free.dev)

# 4. Start the backend
cd backend && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Start the frontend
cd apps/web && pnpm dev
```

> **Important:** Every time you restart ngrok, you get a new URL. You must update the callback URLs in both your `.env` file and in the Linear/Slack app settings.

---

## Linear Integration

### Step 1: Create a Linear OAuth Application

1. Go to [Linear Settings > API](https://linear.app/settings/api)
2. Scroll to **OAuth Applications** and click **Create OAuth Application**
3. Fill in:
   - **Application name:** `ContextOS` (or your project name)
   - **Developer name:** Your name
   - **Callback URLs:** `https://<your-ngrok-url>/api/linear/callback`
4. Leave **Public**, **Client credentials**, and **Webhooks** toggled **off**
5. Click **Create**
6. Copy the **Client ID** and **Client Secret** from the app detail page

### Step 2: Update Environment Variables

Edit the `.env` file in the project root:

```env
LINEAR_CLIENT_ID=<your-client-id>
LINEAR_CLIENT_SECRET=<your-client-secret>
LINEAR_REDIRECT_URI=https://<your-ngrok-url>/api/linear/callback
```

Restart the backend after updating `.env`.

### Step 3: Connect Linear in the Dashboard

1. Open `http://localhost:3000` in your browser
2. Sign in or create an account
3. On the Home page, click **Connect** next to **Linear**
4. You'll be redirected to Linear's OAuth consent page — click **Authorize**
5. If you see ngrok's interstitial warning page, click **Visit Site**
6. You'll be redirected back to the dashboard with Linear showing as **connected**

### Step 4: Sync Linear Tickets

After connecting, tickets need to be synced. This is done via the API:

```bash
# 1. Get your Linear teams
curl -s http://localhost:8000/api/linear/teams \
  -H "Authorization: Bearer <your-jwt-token>"

# 2. Trigger a sync with the team ID
curl -s -X POST http://localhost:8000/api/linear/sync \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{"team_ids": ["<team-id-from-step-1>"]}'
```

The sync runs in the background. It will:
- Fetch all non-cancelled tickets from Linear via GraphQL
- Store them in the `linear_tickets` table
- Generate OpenAI embeddings (768-dim vectors) for each ticket
- Store embeddings in the `embeddings` table for semantic search

> **Tip:** To get a JWT token for curl, you can mint one using the Supabase JWT secret, or use the browser's network tab to copy the token from any authenticated API request.

### Verifying the Sync

Check the database to confirm tickets and embeddings were created:

```bash
# Connect to local Supabase database
docker exec -it $(docker ps --filter "publish=54322" --format "{{.ID}}") \
  psql -U postgres -c "SELECT count(*) FROM linear_tickets;"

docker exec -it $(docker ps --filter "publish=54322" --format "{{.ID}}") \
  psql -U postgres -c "SELECT source_type, count(*) FROM embeddings GROUP BY source_type;"
```

---

## Slack Integration

### Step 1: Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** > **From scratch**
3. Enter an app name (e.g., `ContextOS`) and select your workspace
4. Click **Create App**

### Step 2: Configure Bot Token Scopes

1. In the left sidebar, go to **OAuth & Permissions**
2. Scroll to **Bot Token Scopes**
3. Click **Add an OAuth Scope** and add each of these:
   - `channels:read` — view channel list
   - `channels:history` — read message content
   - `groups:read` — view private channel list
   - `groups:history` — read private channel messages
   - `users:read` — resolve user display names

> **Note:** You must add scopes **before** installing the app. The "App Home" toggles won't work until scopes are added.

### Step 3: Set the Redirect URL

1. Still in **OAuth & Permissions**, scroll to **Redirect URLs**
2. Click **Add New Redirect URL**
3. Enter: `https://<your-ngrok-url>/api/slack/callback`
4. Click **Save URLs**

### Step 4: Copy Credentials

1. Go to **Basic Information** in the left sidebar
2. Copy these three values:
   - **Client ID**
   - **Client Secret**
   - **Signing Secret**

### Step 5: Update Environment Variables

Edit the `.env` file:

```env
SLACK_CLIENT_ID=<your-client-id>
SLACK_CLIENT_SECRET=<your-client-secret>
SLACK_SIGNING_SECRET=<your-signing-secret>
SLACK_REDIRECT_URI=https://<your-ngrok-url>/api/slack/callback
```

Restart the backend after updating.

### Step 6: Connect Slack in the Dashboard

1. Open `http://localhost:3000`
2. Go to the **Integrations** page
3. Click **Connect** next to **Slack**
4. Authorize the app in Slack's consent page
5. You'll be redirected back with Slack showing as **connected**

### Step 7: Select Channels

After connecting, select which channels to monitor:

1. On the **Integrations** page, click **Settings** next to Slack
2. Check the channels you want to ingest messages from
3. Click **Save**

Or via API:

```bash
# List available channels
curl -s http://localhost:8000/api/slack/channels \
  -H "Authorization: Bearer <your-jwt-token>"

# Select channels
curl -s -X POST http://localhost:8000/api/slack/channels/select \
  -H "Authorization: Bearer <your-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{"channel_ids": ["C0ABC123", "C0DEF456"]}'
```

### Step 8: Set Up Real-Time Events (Optional)

For Slack messages to be ingested automatically in real-time:

1. In your Slack app settings, go to **Event Subscriptions**
2. Toggle **Enable Events** on
3. Set the **Request URL** to: `https://<your-ngrok-url>/api/slack/events`
4. Slack will send a verification challenge — the backend handles this automatically
5. Under **Subscribe to bot events**, add:
   - `message.channels` — messages in public channels
   - `message.groups` — messages in private channels (optional)
6. Click **Save Changes**

Now any new message in your selected channels will be automatically:
- Stored in the `slack_messages` table
- Embedded with OpenAI (768-dim vector)
- Available for semantic search and context page generation

> **Note:** The Events API only captures **new** messages going forward. For historical messages, you would need to implement a backfill (see CON-13 ticket).

---

## Testing the AI Pipeline

Once you have data from either Linear or Slack (or both):

### Context Page Generation

1. Go to `http://localhost:3000/dashboard/context`
2. Click the **Ticket Context** tab
3. Enter a ticket identifier (e.g., `CON-16`)
4. Click **Look Up**, then **Generate**
5. The AI will:
   - Find the ticket in the database
   - Search for related content using the linking engine (explicit refs, semantic similarity, keyword matching)
   - Send everything to GPT-4o-mini for synthesis
   - Return a structured context page with: Summary, Background & Decisions, Requirements, Related Work, Open Questions, Key People

### Semantic Search

1. Click the **Semantic Search** tab
2. Type a descriptive query (e.g., `MCP server setup`, `linking algorithm`)
3. Results will show matching content from **all sources** (Tickets, Slack messages) ranked by cosine similarity
4. Each result shows the source type badge and similarity percentage

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Invalid redirect_uri" on OAuth | Update the callback URL in the Linear/Slack app settings to match your current ngrok URL |
| "Internal Server Error" on callback | Check `tail -50 /tmp/backend.log` for the vault permission error. Run the vault function fix (see below) |
| 0 tickets after sync | Wait 15-30 seconds — the sync runs as a background task |
| Search returns 0 results | Use descriptive queries, not ticket IDs. Check that embeddings exist in the database |
| "Failed to fetch" on frontend | Make sure the backend is running on port 8000 |

### Vault Permission Fix

After each `supabase start`, you may need to re-apply the vault function fix:

```bash
docker exec -i $(docker ps --filter "publish=54322" --format "{{.ID}}") psql -U postgres -c "
CREATE OR REPLACE FUNCTION public.store_vault_secret(
  secret_name text, secret_value text, description text default null
) RETURNS uuid AS \$\$
DECLARE existing_id uuid; new_id uuid;
BEGIN
  SELECT id INTO existing_id FROM vault.secrets WHERE name = secret_name;
  IF existing_id IS NOT NULL THEN
    PERFORM vault.update_secret(existing_id, secret_value,
      store_vault_secret.secret_name,
      COALESCE(store_vault_secret.description,
        (SELECT s.description FROM vault.secrets s WHERE s.id = existing_id)));
    RETURN existing_id;
  ELSE
    new_id := vault.create_secret(secret_value, secret_name, COALESCE(description, ''));
    RETURN new_id;
  END IF;
END;
\$\$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = vault, public;"
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `LINEAR_CLIENT_ID` | Yes | From Linear OAuth app settings |
| `LINEAR_CLIENT_SECRET` | Yes | From Linear OAuth app settings |
| `LINEAR_REDIRECT_URI` | Yes | `https://<ngrok-url>/api/linear/callback` |
| `SLACK_CLIENT_ID` | Yes | From Slack app Basic Information |
| `SLACK_CLIENT_SECRET` | Yes | From Slack app Basic Information |
| `SLACK_SIGNING_SECRET` | Yes | From Slack app Basic Information |
| `SLACK_REDIRECT_URI` | Yes | `https://<ngrok-url>/api/slack/callback` |
| `OPENAI_API_KEY` | Yes | For embeddings (text-embedding-3-small) and LLM (gpt-4o-mini) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SUPABASE_URL` | Yes | Local Supabase URL |
| `SUPABASE_KEY` | Yes | Supabase service role key |
| `SUPABASE_JWT_SECRET` | Yes | For verifying user JWT tokens |
