# ✦ Nyota — a multi-vendor marketplace where every shop is a star

Django 5.2 · Channels (live chat) · Celery · PostgreSQL/SQLite · Bootstrap 5 + a custom design system

## Honest status — read this first

This project was written in a sandbox **with no access to PyPI**, so Django itself could never be installed
there. What *was* verified: every Python file compiles, the 35 data-mining unit tests pass, every `{% url %}`,
template include, static file and icon name resolves, template tags are balanced, the generated artwork is valid
XML, and the CSS was rendered in a real browser (screenshots of home, login and dashboard in three themes).
What was **not** possible: running `manage.py`, so **expect a small number of first-run fixes** (a typo, a missing
import). Send me the traceback and it is usually a one-line fix. Migrations were deliberately not generated; you
create them on your machine (step 4).

Also be aware:
* **Real product photos** cannot be bundled. Until a seller uploads one, each product shows generated artwork that
  matches its category, so no card is ever empty. `fetch_product_images` (step 7) pulls matching free photos from
  Wikimedia Commons on *your* machine; items without a confident match keep the artwork and are listed for you.
* **Google/GitHub/Microsoft login, M-Pesa and Stripe** need *your* developer keys. Without keys the site runs in
  **demo mode** (a "Simulate payment" screen), and the login buttons simply don't appear.

## What is inside

| Area | Features |
|---|---|
| Storefront | Hero carousel, scroll rails, shop "constellation", search suggestions, filters, product gallery, reviews, wishlist, 10 themes × 10 accents, twinkling starfield + shooting stars |
| Seller sites | Each shop gets its own page `/shop/<slug>/` with banner, colour, about, hours, social links, **map pin and directions**, follow button, chat button |
| Orders | Cart per shop, coupons, checkout with **map delivery pin**, orders split per seller (commission snapshot), stock locking |
| Tracking | Seller **or admin** moves each part through pending → delivered with dated events + map points; customers see a stepper, timeline and journey map; public lookup by order no. + phone at `/track/` |
| Payments | M-Pesa Daraja STK push (+ callback), Stripe Checkout (+ webhook), cash on delivery, idempotent confirmation, demo mode |
| Chat | Customer ↔ seller ↔ admin/support: **reply, react, delete (soft), emoji**, WebSocket with HTTP polling fallback |
| Portals | Customer, Seller owner, **Seller staff (assistants, permission per position)**, Admin, Analyst, Developer, CEO, Support |
| Identity | Three login doors (`/login/`, `/seller/login/`, `/staff/login/`); staff usernames/emails generated from **name + position + company** (e.g. `jane.kamau.ceo@nyota.market`, `lucy.sang.cashier@savanna-tech.nyota.market`); forced password change on first login |
| Accounts | Email verification, password recovery, login with Google/GitHub/Microsoft, lockout after 5 failures |
| Staff | Attendance (clock in/out, lateness), shop team management |
| Audit | Append-only audit log with a SHA-256 hash chain and an integrity check (Developer portal) |
| Seller verification | Sellers upload ID, KRA PIN, address proof (+ company registration) and accept the anti-fraud policy; an **administrator checks, the CEO approves** (two-person rule); only then is the shop public and payouts unlock. Documents are stored privately and every view is audited |
| Profiles | `/people/<username>/`: what you see depends on the relationship (customer card, shop to its customers, colleagues, Nyota team) and on each member's privacy setting |
| Usage & errors | Page views, searches, cart/order steps feed the analyst **Usage** and **Data warehouse** pages; every crash gets a reference (NY-XXXXXX) that support can search, grouped into tickets in the **Error tracker**; browser JS errors are reported too; support can open a member's **timeline** (activity, errors, audit trail) |
| Payroll | Ranks (base salary) x job categories (% allowance) + overtime, minus absence, lateness and PAYE/NSSF/SHIF/housing levy. Platform staff: administrator prepares, CEO approves. Each shop owner runs their own team's payroll. Staff read payslips under *My payslips* |
| Analytics | Star-schema warehouse (`DimDate/Shop/Product/Customer`, `FactSales`) + mining: RFM segments, market-basket rules, ABC/Pareto, Holt forecast, anomaly detection, review sentiment |
| API | `/api/v1/products/`, `/api/v1/shops/`, `/api/v1/orders/` (yours), `/api/v1/me/`, `/api/health/` with token auth |

## Run it on Windows (PowerShell)

Requirements: Python 3.11+ (3.12 recommended). Postgres and Redis are optional.

```powershell
cd nyota
python -m venv venv
.\venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt

copy .env.example .env               # then edit .env: at least set SECRET_KEY

# 4. create the database tables (migrations were not pre-generated)
python manage.py makemigrations
python manage.py migrate

# 5. demo data: staff for every role, 6 shops, ~45 products, ~220 orders, chats, reviews, warehouse
python manage.py seed_demo
python manage.py payroll_defaults --shops   # default ranks, categories and pay profiles (seed_demo already does this)
python manage.py fetch_vendor               # optional: store Bootstrap/Leaflet/Chart.js locally so pages never wait for a CDN
python manage.py createsuperuser     # optional, for /django-admin/

# 6. run (Daphne serves HTTP + WebSockets)
python manage.py runserver
```

Open <http://localhost:8000>. `seed_demo` prints every demo login at the end; they all share the password
`Nyota@2026!`. Try, in separate browsers/profiles so sessions don't clash:

* Customer `/login/` · Seller `/seller/login/` · Staff `/staff/login/` (admin, analyst, developer, ceo, support)
* As a seller, update an order's tracking → the customer's order page updates with dates and map.
* As a customer, message a shop; the seller replies from **Messages** in real time.

```powershell
# 7. (optional) real product photos from Wikimedia Commons: run on your machine
python manage.py fetch_product_images --dry-run
python manage.py fetch_product_images
```

### Optional: Redis, Celery, Postgres

* `REDIS_URL=redis://localhost:6379/0` enables live chat across several processes and a real Celery worker:
  `celery -A config worker -B -l info`. Without it, chat uses an in-memory layer and Celery runs inline.
* `DATABASE_URL=postgres://user:pass@localhost:5432/nyota` switches from SQLite to PostgreSQL (full-text search
  turns on automatically).
* Or everything at once: `docker compose up --build` (Postgres + Redis + web + worker), then run
  `docker compose exec web python manage.py makemigrations ...` the first time.

## Turning on real integrations

| Feature | What you need |
|---|---|
| Google sign-in | Google Cloud → OAuth client; redirect URI `http://localhost:8000/oauth/google/callback/`; set `GOOGLE_CLIENT_ID/SECRET` |
| M-Pesa | Safaricom Daraja app (sandbox is fine), `MPESA_*` keys, and `MPESA_CALLBACK_URL` = your public HTTPS **base URL only** (e.g. `https://abc.ngrok-free.app`, use ngrok locally); the app appends `/payments/mpesa/callback/<token>/` itself |
| Stripe | `STRIPE_SECRET_KEY`, and `stripe listen --forward-to localhost:8000/payments/stripe/webhook/` for the secret |
| Email | `EMAIL_HOST…`; with none set, emails print in the terminal |
| Shop subdomains | `ROOT_DOMAIN=yourdomain.com` + wildcard DNS: `slug.yourdomain.com` opens that shop |

## Hosting later

`Dockerfile`, `docker-compose.yml`, `Procfile` and `render.yaml` are included. For production set
`DEBUG=False`, a long `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `REDIS_URL`, and run behind HTTPS.
Static files are served by WhiteNoise; uploaded media (`MEDIA_ROOT`) needs persistent storage or S3.

## Tests

```powershell
python manage.py test            # Django tests + 35 data-mining tests
```

## Project map

```
config/      settings, ASGI (HTTP + WebSocket), Celery
accounts/    users, roles, staff identities, OAuth, email verification, attendance
shops/       shop profiles, team permissions        catalog/   products, reviews, search
orders/      cart, checkout, split orders, tracking  payments/  M-Pesa, Stripe, webhooks
chat/        conversations, consumers, HTTP API      audit/     hash-chained audit log
analytics/   warehouse ETL + data mining             portals/   every dashboard
core/        storefront, theme system, SVG artwork, seed_demo   api/  REST
templates/ static/   the interface
```


##  CLONE
```powershell
git clone https://github.com/brandoenkimu/Nyota.git
cd Nyota
```
=======
