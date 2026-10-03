# KaziBuddy — Backend

Django REST API for **[KaziBuddy](https://kazibuddy.tech)**, a job marketplace that connects semi-skilled workers with employers. Users register, get verified by an admin, post or apply for jobs, track assignments, and message each other in real time.

---

## Links

| | |
|---|---|
| 🌐 Live site | https://kazibuddy.tech |
| 🔌 Live API | https://api.kazibuddy.tech/api/ |
| 🖥️ Frontend repo | [Tafakari-Org/kazibuddy-frontend](https://github.com/Tafakari-Org/kazibuddy-frontend) |
| ⚙️ Backend repo | [Tafakari-Org/kazibuddy-backend](https://github.com/Tafakari-Org/kazibuddy-backend) |
| 📘 Frontend setup | [kazibuddy-frontend → Getting started](https://github.com/Tafakari-Org/kazibuddy-frontend#getting-started) |
| 📗 Backend setup | [kazibuddy-backend → Getting started](https://github.com/Tafakari-Org/kazibuddy-backend#getting-started-docker-recommended) |

---

## Tech stack

| Area | Tooling |
|---|---|
| Framework | Django 5.2, Django REST Framework |
| Auth | JWT (`djangorestframework-simplejwt`), Google OAuth (`dj-rest-auth` + `django-allauth`), email OTP verification |
| Database | PostgreSQL 17 |
| Real-time | Django Channels + Redis (WebSocket messaging), served by Daphne (ASGI) |
| Background jobs | Celery (Redis broker) |
| File storage | Local disk under `tafakari/uploads/`, served at `/media/` |
| Runtime | Docker / Docker Compose, Python 3.13 image |

---

## Project layout

```
kazibuddy-backend/
├── Dockerfile
├── docker-compose.yml        # local development stack
├── docker-compose.prod.yml   # production stack
├── Makefile                  # shortcuts for common tasks (run `make help`)
├── entrypoint.sh
├── scripts/deploy.sh         # production deploy script (run by CI)
├── .github/workflows/        # CI: deploy on push to `deployment`
└── tafakari/                 # Django project root (manage.py lives here)
    ├── tafakari/             # settings, urls, asgi, celery config
    ├── accounts/             # custom user model, registration, OTP, login, profile
    ├── workers/              # worker profile models (API routes currently removed)
    ├── employers/            # employer profile models
    ├── jobs/                 # job posting, listing, images and attachments
    ├── applications/         # job applications
    ├── assignments/          # assigned jobs and their lifecycle
    ├── skills/               # skills and categories
    ├── documents/            # user documents (upload, list, download, delete)
    ├── messaging/            # real-time chat (Channels consumers)
    ├── ratings/              # reviews and ratings
    ├── adminpanel/           # admin approval of users and jobs
    ├── analytics/            # admin analytics
    ├── payments/             # payments (work in progress, not yet enabled)
    └── utils/                # shared helpers (file uploads, email, OTP)
```

---

## API overview

All endpoints are under `/api/`. Authenticated endpoints expect `Authorization: Bearer <access token>`.

| Prefix | Purpose |
|---|---|
| `/api/accounts/` | Register, verify email (OTP), log in, refresh tokens, password reset, own profile (`me/`) |
| `/api/v1/auth/` | dj-rest-auth endpoints and Google OAuth login/callback |
| `/api/jobs/` | Jobs: create, list, search, update, delete |
| `/api/applications/` | Apply to jobs, review applications |
| `/api/assignments/` | Assigned jobs |
| `/api/skills/` | Skills and categories |
| `/api/documents/` | Current user's documents (see below) |
| `/api/messages/` | Conversations and messages |
| `ws/thread/<thread_id>/` | WebSocket for live chat in a thread |
| `/api/adminpanel/` | Admin-only user and job moderation |
| `/media/<path>` | Uploaded files |
| `/admin/` | Django admin |

### Documents

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/documents/mine/` | List your documents and storage usage |
| `POST` | `/api/documents/mine/` | Upload one document (`file` field, multipart) |
| `DELETE` | `/api/documents/mine/<id>/` | Delete one of your documents |
| `GET` | `/api/documents/mine/<id>/download/` | Download one of your documents (original filename) |
| `GET` | `/api/adminpanel/users/<user_id>/documents/<id>/download/` | Admin only: stream any user's document for review before approval or job assignment |

Limits:
- **Per user:** at most **10 documents in total** (academic documents, images, anything else), counting both signup and profile uploads.
- **Registration:** up to **10** supporting documents (`academic_documents`), max **5 MB** each.
- **Profile uploads:** max **5 MB** per file, **50 MB** total per user.
- Allowed types: PDF, Word, Excel, TXT, JPG/PNG.

---

## Getting started (Docker, recommended)

**Prerequisites:** Docker and Docker Compose.

1. Clone the repo:
   ```bash
   git clone https://github.com/Tafakari-Org/kazibuddy-backend.git
   cd kazibuddy-backend
   ```
2. Create the env file the local stack reads (`tafakari/.env`), using `.env.docker.example` as the template:
   ```bash
   cp .env.docker.example tafakari/.env
   ```
   Fill in at least `SECRET_KEY`, the database credentials, email settings and Google OAuth keys (see [Environment variables](#environment-variables)).
3. Start everything:
   ```bash
   make up        # or: docker compose up -d
   make migrate
   ```
4. Open:
   - API: http://localhost:8000/api/
   - Django admin: http://localhost:8000/admin/

   To run the UI against it, follow the [frontend setup](https://github.com/Tafakari-Org/kazibuddy-frontend#getting-started) with `NEXT_PUBLIC_BASE_URL=http://localhost:8000/api`.

Optional sample data:
```bash
make seed-all   # seed users, then seed jobs
```

### Local services

| Service | Container | Port |
|---|---|---|
| `web` | Django on Daphne | `8000` |
| `celery` | Celery worker | — |
| `db` | PostgreSQL 17 | `5432` |
| `redis` | Redis | `6380` on host → `6379` in container |

### Useful `make` targets

| Command | What it does |
|---|---|
| `make up` / `make down` | Start / stop all services |
| `make restart` | Restart `web` and `celery` after code changes |
| `make rebuild` | Rebuild images and restart |
| `make logs`, `make logs-web`, `make logs-celery` | Tail logs |
| `make migrate` | Apply migrations |
| `make migrations APP=<app>` | Create migrations |
| `make shell` / `make bash` / `make db-shell` | Django shell / container shell / psql |
| `make seed`, `make seed-jobs`, `make seed-all` (`-flush` variants) | Seed sample data |
| `make test` | Run the Django test suite |
| `make lint` | Run flake8 |

Run `make help` for the full list.

---

## Getting started (without Docker)

You need Python 3.12+, PostgreSQL and Redis running locally.

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cd tafakari
# create tafakari/.env (see Environment variables)
python manage.py migrate
python manage.py createsuperuser  # optional
daphne -b 0.0.0.0 -p 8000 tafakari.asgi:application   # or: python manage.py runserver
```

In another terminal, start the Celery worker:
```bash
cd tafakari && celery -A tafakari worker --loglevel=info
```

---

## Environment variables

Templates: `.env.docker.example` (local) and `.env.prod.example` (production). Never commit real values.

| Group | Variables |
|---|---|
| Django | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `SITE_ID`, `FRONTEND_URL` |
| Database | `DATABASE_URL` or `POSTGRES_NAME` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `DB_HOST` / `DB_PORT` |
| Redis / Celery | `REDIS_HOST`, `REDIS_PORT`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| CORS / CSRF | `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_ALL_ORIGINS`, `CORS_ALLOW_CREDENTIALS`, `CSRF_TRUSTED_ORIGINS` |
| Email (OTP, notifications) | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_SSL` (`True` for port 465; `False` switches to STARTTLS for 587) |
| Google OAuth | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_CALLBACK_URL` |
| Supabase | `SUPABASE_URL`, `SUPABASE_KEY` |

---

## Branches and deployment

| Branch | Purpose |
|---|---|
| `deployment` | Production. Every push triggers the GitHub Actions workflow, which SSHes into the VPS and runs `scripts/deploy.sh` (rebuild containers, migrate, collect static). |
| `main` | Default branch. |
| `test`, feature branches | Work in progress; merged via pull request. |

Because each push to `deployment` triggers a deploy, avoid pushing to it several times in quick succession. Overlapping deploys can fail with Docker container-name conflicts.

---

## Running tests

```bash
make test
# or, without Docker:
cd tafakari && python manage.py test
```
