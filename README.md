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

**Needs:** Python **3.12+**, **Postgres**. **Docker** only for Compose or `pytest`.

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

| Table | Main idea |
|-------|-----------|
| **users** | Login; unique `email`; `password` (bcrypt); `search_vector` for FTS |
| **organization** | `org_id`, `org_name` |
| **membership** | `(org_id, user_id)` + `role` (`admin` / `member`) |
| **items** | `org_id`, `user_id`, `item_details` (JSONB) |
| **audit_log** | Who did what; optional `details` JSONB; org/user FKs nullable on delete |

Users ↔ orgs is **many-to-many** through **membership**. Items and audit rows belong to an org.

---

## Tradeoffs (brief)

- **Schema from models** — simple; changing columns later needs manual DB updates or a future migration tool if you outgrow `create_all`.
- **JWT** — simple scaling; instant revoke needs extra design if you need it.
- **Tenancy in app code** — clear checks; DB row-level security could be added later.
- **JSONB** — flexible; validate important fields in the API when it matters.

---

## API cheat sheet

- `POST /auth/register`, `POST /auth/login`
- `POST /organizations/` — create org
- `GET /organizations/{id}/users`, `GET .../users/search?q=` — members (**admin**)
- `POST /organizations/{id}/user` — invite by email (**admin**)
- `GET|POST /organizations/{id}/item` — items
- `GET /organizations/{id}/audit-logs`, `POST .../audit-logs/ask` — audit + chat (**admin**)

Protected routes: **`Authorization: Bearer <token>`**. Don’t commit secrets.
