# Reflex — delivery coordination for small Kenyan retailers

Retailer logs a delivery → dispatcher assigns a rider → rider scans a QR
code at pickup and delivery. Every status change is recorded, so nothing
depends on a WhatsApp thread anyone can lose track of.

## Run it locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo        # creates demo retailer/dispatcher/rider accounts
python manage.py runserver
```

Visit `http://localhost:8000`. Demo logins (password for all: `reflex2026`):

| Username | Role |
|---|---|
| `retailer1` | Retailer staff |
| `dispatcher1` | Dispatcher |
| `rider1`, `rider2` | Rider |

Admin panel at `/admin/` — create your own superuser with
`python manage.py createsuperuser` if you need one beyond the seeded demo data.

## Deploy to Render (free tier, ~5 minutes)

1. Push this project to a GitHub repo (see below if you want me to do this part).
2. Go to [render.com](https://render.com) → sign up / log in → **New +** → **Blueprint**.
3. Connect your GitHub account and pick this repo. Render will read `render.yaml`
   automatically and show you a plan: one **Postgres** database (free) and one
   **web service** (free).
4. Click **Apply**. Render will:
   - Provision the free Postgres database.
   - Run `pip install -r requirements.txt` and `collectstatic`.
   - Run migrations, then start the app with gunicorn.
5. Once it says "Live" (takes 2–4 minutes on first deploy), open the URL Render
   gives you — something like `https://reflex-xxxx.onrender.com`.
6. Open the Render **Shell** tab for the web service and run:
   ```bash
   python manage.py seed_demo
   python manage.py createsuperuser
   ```
   This seeds the same demo accounts on the live database.

That's it — no manual env var typing required, `render.yaml` sets
`SECRET_KEY` (auto-generated), `DEBUG=False`, `ALLOWED_HOSTS`, and
`DATABASE_URL` (wired to the Postgres instance) for you.

### If you'd rather use Railway / another host
The app is a standard Django project with `whitenoise` for static files and
`dj-database-url` for the DB connection, so it works on Railway, Fly.io, or
PythonAnywhere too — just set `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`,
and `ALLOWED_HOSTS` as env vars there instead, and use the same build/start
commands from `render.yaml`.

## Project structure

```
reflex_project/       Django settings, root URLs
delivery/
  models.py            DeliveryRequest, StatusEvent, UserProfile
  views.py             role-based dashboards + DRF API endpoints
  serializers.py       DRF serializers
  templates/delivery/  server-rendered dashboards (retailer/dispatcher/rider)
  management/commands/seed_demo.py   creates demo accounts
```

## Known simplifications (see the trade-off log for the full defense)

- **Polling, not WebSockets**: dashboards auto-refresh every 5 seconds via
  plain `fetch()` rather than push over Channels/Redis. Faster to build and
  deploy reliably on a free-tier host; the cost is up to a 5-second lag and
  more requests than a push model needs at scale.
- **SMS notifications are not wired up**: the code path exists at the point
  where a real send would happen (see `StatusEvent` creation in
  `DeliveryRequest.apply_transition`), but no Africa's Talking account is
  configured for the demo.
- **QR scan has a manual-code fallback**: if the camera API isn't available
  in the browser or lighting is poor, the rider can type/paste the code
  shown under the retailer's delivery card instead.
