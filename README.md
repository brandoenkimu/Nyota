# ✦ Nyota: a multi-vendor marketplace where every shop is a star

Django 5.2 · Channels (live chat) · Celery · PostgreSQL/SQLite · Bootstrap 5 + a custom design system

Nyota lets sellers open verified shops, customers buy with M-Pesa, card or cash on delivery, and staff run the
platform through role-based portals. It also includes a data warehouse for analysts, a full audit trail, error
tracking for support, and payroll for staff.

## Honest status

This project was built in a sandbox with no access to PyPI, so some code could only be checked by compiling it, not by running it.

* Verified: Python and JavaScript files compile, the data-mining unit tests pass, and templates, URLs and static files resolve.
* Not verified: a full `manage.py` run. Expect a few first-run fixes (a typo or a missing import). Send the traceback and it is usually a one-line fix.
* Migrations are not pre-generated. Create them on your machine (see Run it).
* Google/GitHub/Microsoft login, M-Pesa and Stripe need your own developer keys. Without keys the site runs in **demo mode** (a "Simulate payment" screen), and the social login buttons do not appear.
* Real product photos cannot be bundled. Generated artwork is shown until a seller uploads a photo.

## What is inside

| Area | Features |
|---|---|
| Storefront | Hero carousel, scroll rails, shop constellation, search suggestions, filters, product gallery, reviews, wishlist, 10 themes × 10 accents, twinkling starfield |
| Seller sites | Each shop has `/shop/<slug>/` with banner, colour, about, hours, social links, map pin, follow and chat buttons |
| Seller verification | Sellers upload supporting documents (ID, business registration, tax and permit papers). Admins and CEOs review and approve them in a review queue. Unverified shops cannot sell, which protects buyers from scams |
| Orders | Cart per shop, coupons, checkout with map delivery pin, orders split per seller, commission snapshot, stock locking |
| Order safety | Sellers only see orders that are paid or pay-on-delivery. Customers can cancel an unpaid order (stock is restored). Unpaid online orders auto-cancel after 60 minutes via Celery. Late payments on cancelled orders are flagged in the audit log for refund |
| Tracking | Seller or admin moves each part through pending → delivered with dated events and map points. Customers see a stepper, timeline and journey map. Public lookup at `/track/` |
| Payments | M-Pesa Daraja STK push, Stripe Checkout with webhook, cash on delivery, idempotent confirmation, demo mode |
| Chat | Customer ↔ seller ↔ admin/support with reply, react, soft delete, emoji. WebSocket with HTTP polling fallback |
| Portals | Customer, Seller owner, Seller staff, Admin, Analyst, Developer, CEO, Support |
| Public profiles | Directional profile pages: customers see other customers, and staff see other staff, with each view limited by who is looking at whom |
| Identity | Three login doors (`/login/`, `/seller/login/`, `/staff/login/`), staff identities generated from name + position + company, forced password change on first login |
| Accounts | Email verification, password recovery, social login, lockout after 5 failed attempts |
| Themes | Auto (follows the device), saved per device, falls back to the account setting, no wrong-theme flash on load |
| Login transition | The warp animation is capped so the redirect never hangs |
| Staff | Attendance (clock in/out, lateness), shop team management |
| Payroll | Pay grades by rank and job category, payroll runs and payslips for staff |
| Analytics | Star-schema warehouse (`DimDate/Shop/Product/Customer`, `FactSales`), activity events, and mining: RFM segments, market-basket rules, ABC/Pareto, forecasting, anomaly detection, review sentiment |
| Audit | Append-only audit log with a SHA-256 hash chain and an integrity check in the Developer portal |
| Error tracking | `ErrorLog` with server middleware and client-side error reporting. Support staff and admins can trace a user's problem and see it next to the audit trail |
| API | `/api/v1/products/`, `/api/v1/shops/`, `/api/v1/orders/`, `/api/v1/me/`, `/api/health/` with token auth |
| Performance | Third-party CSS/JS (Bootstrap, Leaflet, Chart.js) can be served locally and otherwise load without blocking the page |

## Run it on Windows (PowerShell)

Requirements: Python 3.11+ (3.12 recommended). Postgres and Redis are optional.

```powershell
cd nyota
python -m venv venv
.\venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt

copy .env.example .env               # then edit .env: at least set SECRET_KEY

python manage.py makemigrations accounts shops catalog orders payments chat audit analytics core
python manage.py migrate

python manage.py seed_demo           # demo staff, shops, products, orders, chats, warehouse
python manage.py createsuperuser     # optional, for /django-admin/

python manage.py runserver
```

Open <http://localhost:8000>. `seed_demo` prints every demo login at the end; they share the password `Nyota@2026!`.
Use separate browsers or profiles so sessions do not clash.

Optional commands:

```powershell
python manage.py fetch_vendor             # download Bootstrap/Leaflet/Chart.js into static/vendor
python manage.py fetch_product_images     # real product photos from Wikimedia Commons
python manage.py expire_unpaid_orders     # cancel abandoned unpaid orders now
```

### Optional: Redis, Celery, Postgres

* `REDIS_URL=redis://localhost:6379/0` enables live chat across processes and a real Celery worker:
  `celery -A config worker -B -l info`. Without it, chat uses an in-memory layer and Celery runs inline.
  Celery beat runs the unpaid-order expiry every 15 minutes.
* `DATABASE_URL=postgres://user:pass@localhost:5432/nyota` switches from SQLite to PostgreSQL.
* Or run everything with `docker compose up --build`.

## Turning on real integrations

| Feature | What you need |
|---|---|
| Google sign-in | Google Cloud OAuth client; redirect URI `http://localhost:8000/oauth/google/callback/`; set `GOOGLE_CLIENT_ID/SECRET` |
| M-Pesa | Safaricom Daraja app, `MPESA_*` keys, and a public HTTPS `MPESA_CALLBACK_URL` (use ngrok locally) |
| Stripe | `STRIPE_SECRET_KEY`, and `stripe listen --forward-to localhost:8000/payments/stripe/webhook/` |
| Email | `EMAIL_HOST…`; with none set, emails print in the terminal |
| Shop subdomains | `ROOT_DOMAIN=yourdomain.com` plus wildcard DNS |

Tunable setting: `PAYABLE_AFTER_MINUTES = 60` in `orders/services.py` (abandoned-order window).

## Privacy and security notes

* Seller verification documents are sensitive. They live in `media/`, which is git-ignored. Use private storage in production and never commit them.
* Never commit `.env`. Commit only `.env.example`.
* Before going live: `DEBUG=False`, a long `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, HTTPS, then `python manage.py check --deploy`.

## Hosting

`Dockerfile`, `docker-compose.yml`, `Procfile` and `render.yaml` are included. Static files are served by WhiteNoise.
Uploaded media needs persistent storage or S3.

## Tests

```powershell
python manage.py test
```

## Project map

```
config/      settings, ASGI (HTTP + WebSocket), Celery
accounts/    users, roles, staff identities, OAuth, verification, attendance, payroll
shops/       shop profiles, team permissions, seller verification
catalog/     products, reviews, search
orders/      cart, checkout, split orders, tracking, cancel and expiry
payments/    M-Pesa, Stripe, webhooks
chat/        conversations, consumers, HTTP API
audit/       hash-chained audit log
analytics/   warehouse ETL, activity events, data mining
portals/     every dashboard and review queue
core/        storefront, themes, artwork, error tracking, seed_demo
api/         REST
templates/ static/   the interface
```