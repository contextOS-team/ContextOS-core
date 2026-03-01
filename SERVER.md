# ContextOS Server Infrastructure

## Server Access

| Field | Value |
|-------|-------|
| Provider | Timeweb Cloud |
| IP | `85.239.57.166` |
| SSH | `ssh root@85.239.57.166` |
| Password | `r.iXcpT1k87+L+` |
| Domain | `contextos.pro` |
| OS | Ubuntu 24.04 |
| RAM | 1 GB + 2 GB swap |

> **Warning:** Server is currently located in **Russia**. Linear API is blocked from Russian IPs. Migration to Netherlands/EU server is needed for OAuth integrations to work.

## URLs

| Service | URL |
|---------|-----|
| Frontend | https://contextos.pro |
| Backend API | https://api.contextos.pro |
| API Docs (Swagger) | https://api.contextos.pro/docs |

## Running Services

| Service | Command to check |
|---------|-----------------|
| Backend (FastAPI/Uvicorn) | `systemctl status contextos-api` |
| Frontend (Next.js) | `systemctl status contextos-app` |
| Nginx (reverse proxy + SSL) | `systemctl status nginx` |
| Redis (caching) | `systemctl status redis` |

## File Locations

```
/opt/contextos/                        # App root
├── .env                               # Backend environment variables
├── backend/
│   ├── src/                           # FastAPI application
│   └── .venv/                         # Python virtual environment
├── apps/
│   └── web/
│       ├── .env.local                 # Frontend environment variables
│       └── .next/                     # Built frontend
└── supabase/
    └── migrations/                    # Database migrations

/etc/nginx/sites-available/
├── contextos-api                      # Nginx config for api.contextos.pro
└── contextos-app                      # Nginx config for contextos.pro

/etc/systemd/system/
├── contextos-api.service              # Backend systemd service
└── contextos-app.service              # Frontend systemd service

/etc/letsencrypt/live/contextos.pro/   # SSL certificates (Let's Encrypt)
```

## Database

| Field | Value |
|-------|-------|
| Provider | Supabase (hosted) |
| Region | ap-southeast-1 |
| Project ref | `hwgetjvfmacktjohflku` |
| Dashboard | https://supabase.com/dashboard/project/hwgetjvfmacktjohflku |
| Connection | `postgresql+asyncpg://postgres.hwgetjvfmacktjohflku:***@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres` |

## DNS (Namecheap)

| Record | Type | Value |
|--------|------|-------|
| `contextos.pro` | A | `85.239.57.166` |
| `api.contextos.pro` | A | `85.239.57.166` |
| `app.contextos.pro` | A | `85.239.57.166` |

## OAuth Integrations

| Provider | Dashboard | Callback URL |
|----------|-----------|-------------|
| Linear | https://linear.app/settings/api | `https://api.contextos.pro/api/linear/callback` |
| Slack | https://api.slack.com/apps | `https://api.contextos.pro/api/slack/callback` |
| GitHub | GitHub Developer Settings → GitHub Apps → ContextOS-app | `https://api.contextos.pro/api/github/callback` |
| Notion | https://www.notion.so/profile/integrations | `https://api.contextos.pro/api/notion/callback` |

## Common Commands

```bash
# Restart services
sudo systemctl restart contextos-api
sudo systemctl restart contextos-app
sudo systemctl restart nginx

# View logs (live)
journalctl -u contextos-api -f
journalctl -u contextos-app -f

# View recent logs
journalctl -u contextos-api --since "30 minutes ago" --no-pager

# Deploy code update
cd /opt/contextos
git pull
# Backend: just restart
sudo systemctl restart contextos-api
# Frontend: rebuild then restart
cd apps/web && npm run build && cd ../..
sudo systemctl restart contextos-app
```
