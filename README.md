# Multi-Tenant Organization Manager

API for **organizations**, **members** (admin / member), **items** (JSON), **audit logs**, **member search**, and **optional OpenAI** over audit data.

**Repo:** https://github.com/Aydie-yasser/FastAPIProject

---

## Architecture (short)

- **FastAPI + sync SQLAlchemy** — one DB session per request; **psycopg** to Postgres; tables are created from models on app **startup** (`create_all`).
- **Postgres** — relational data + **JSONB** for flexible payloads + **full-text search** on member name/email (GIN index on `users.search_vector`).
- **JWT** — `Authorization: Bearer`; org **admin** vs **member** enforced in **services**.
- **Thin routes, fat services** — HTTP in `app/routes/`, rules in `app/services/`, DTOs in `app/schemas/`.
- **OpenAI** — audit Q&A only if `OPENAI_API_KEY` is set; otherwise a short fallback message.

---

## Run locally

**Needs:** Python **3.15+** locally (or match the Docker image). **Postgres**. **Docker** only for Compose or `pytest`.

The **`Dockerfile`** uses **`python:3.15-rc-slim-bookworm`** (official pre-release / RC build). When Python **3.15.x** is stable, you can switch the tag to **`python:3.15-slim-bookworm`** if that image exists on Docker Hub.

Create **`.env`** (Postgres on your machine — use `127.0.0.1`, not `db`):

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DBNAME
JWT_SECRET_KEY=<long random secret>
```

Generate a secret: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`  
Optional: `OPENAI_API_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (see `app/config.py`).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The app creates missing tables when it starts. Docs: **http://127.0.0.1:8000/docs** · DB check: **`/db/health`**

**Tests** (Docker must be running):

```bash
pip install pytest pytest-asyncio "testcontainers[postgres]" httpx
pytest
```

---

## Docker Compose

Create **`.env`** with Postgres vars and a `DATABASE_URL` that uses host **`db`** for the `web` service, for example:

```env
POSTGRES_DB=appdb
POSTGRES_USER=appuser
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql+psycopg://appuser:change_me@db:5432/appdb
JWT_SECRET_KEY=<long random secret>
```

```bash
docker compose up --build      # API on :8000; tables created on startup
docker compose down            # stop (keeps volume)
docker compose down -v         # stop + wipe DB volume
```

**`docker-compose.yml`:** Postgres 16 + healthcheck + `web` build from `Dockerfile`.

---

## Database

Postgres holds all application data. On startup the app runs **`create_all`** from SQLAlchemy models (see `app/db/schema.py` and `app/models/`). There is no separate migration CLI in this repo.

### Tables and columns

**`users`** — global accounts (not tied to one org by themselves).

| Column | Notes |
|--------|--------|
| `id` | Primary key. |
| `full_name`, `email` | `email` is unique (indexed). |
| `password` | Bcrypt hash (never returned by the API). |
| `search_vector` | PostgreSQL `tsvector`, **generated** from `full_name` + `email` for English full-text search; **GIN** index for fast `@@` queries. |

**`organization`** — a tenant / company.

| Column | Notes |
|--------|--------|
| `org_id` | Primary key. |
| `org_name` | Display name. |

**`membership`** — links a user to an org with a **role** (RBAC is **per org**).

| Column | Notes |
|--------|--------|
| `org_id`, `user_id` | **Composite primary key**; both are foreign keys (`ON DELETE CASCADE`). |
| `role` | `"admin"` or `"member"` (string). |

**`items`** — arbitrary records inside an org.

| Column | Notes |
|--------|--------|
| `item_id` | Primary key. |
| `org_id`, `user_id` | Owning org and creating user (FKs, `ON DELETE CASCADE`). |
| `created_at` | Timestamp (timezone-aware), server default `now()`. |
| `item_details` | **JSONB** — any JSON object the client sends; no fixed schema in the DB. |

**`audit_log`** — append-only style events for compliance / debugging.

| Column | Notes |
|--------|--------|
| `audit_id` | Primary key. |
| `created_at` | When the event was recorded. |
| `org_id`, `user_id` | Optional FKs, **`ON DELETE SET NULL`** so rows remain if a user or org row is removed. |
| `action` | Short label, e.g. `item.create`, `organization.create`. |
| `resource_type`, `resource_id` | What entity was affected (optional id). |
| `details` | Optional **JSONB** payload (e.g. copied item fields). |

### How things connect

- A **user** can belong to **many orgs**; an **org** has **many members** → **`membership`** is the join table.
- **Items** always belong to one **org** and one **creator user**.
- **Audit** rows usually reference an **org** and sometimes the **actor user**; they are listed per org in the API.

---

## APIs

Base URL is your server (e.g. `http://127.0.0.1:8000`). Interactive docs: **`/docs`**. Most org routes need a JWT.

### Authentication header

After login, send:

```http
Authorization: Bearer <access_token>
```

Without a valid token, protected routes return **401**. Wrong password on login returns **401**.

### Auth (`/auth`)

| Method | Path | Body | Who |
|--------|------|------|-----|
| POST | `/auth/register` | `{ "full_name", "email", "password" }` | Public; **409** if email exists. |
| POST | `/auth/login` | `{ "email", "password" }` | Public; returns `{ "access_token", "token_type": "bearer" }`. |

### Organizations (`/organizations`)

Prefix: **`/organizations`**. `{id}` is the **`org_id`**.

| Method | Path | Auth | What it does |
|--------|------|------|----------------|
| POST | `/` | JWT | Create org; creator becomes **admin**. **201** + org payload. |
| GET | `/{id}/users` | JWT **admin** of that org | Paginated members: query `limit` (default 20, max 100), `offset`. Response: `Page` with `items` (`user_id`, `full_name`, `email`, `role`), `total`, `limit`, `offset`. |
| GET | `/{id}/users/search` | JWT **admin** | Same member shape; query **`q`** (required) for **full-text** search on name + email; same pagination params. |
| POST | `/{id}/user` | JWT **admin** | Invite: `{ "email", "role": "admin" \| "member" }`. Target user must **already be registered**. **201** or **404** / **409** / **403**. |
| GET | `/{id}/item` | JWT **member** of org | List items: **members** see only **their** items; **admins** see **all** in the org. Paginated `Page` of items. Each call appends **`audit_log`** (`item.list`). |
| POST | `/{id}/item` | JWT **member** | Create item: `{ "item_details": { ...any JSON... } }`. **201** `{ "item_id" }`; also writes **`audit_log`** (`item.create`). |
| GET | `/{id}/audit-logs` | JWT **admin** | Paginated **`audit_log`** rows for that org. |
| POST | `/{id}/audit-logs/ask` | JWT **admin** | Body: `{ "question": "...", "stream": false }`. Loads recent logs + calls OpenAI if configured; **`stream: true`** returns **plain text** chunks. **200** JSON `{ "answer" }` or streamed body. |

### Other routes

| Method | Path | Notes |
|--------|------|--------|
| GET | `/` | Hello message. |
| GET | `/db/health` | Runs `SELECT 1`; checks DB connectivity. |

### Common HTTP codes

- **403** — Authenticated but not allowed (e.g. member hitting an admin-only route, or user not in that org).
- **404** — Org not found, or invited email has no user account.
- **409** — Conflict (e.g. duplicate membership).
- **502** — Upstream LLM error on audit Q&A (non-streaming path).

---

## Tradeoffs (brief)

- **Schema from models** — simple; changing columns later needs manual DB updates or a future migration tool if you outgrow `create_all`.
- **JWT** — simple scaling; instant revoke needs extra design if you need it.
- **Tenancy in app code** — clear checks; DB row-level security could be added later.
- **JSONB** — flexible; validate important fields in the API when it matters.

---
