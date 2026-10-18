# helpdesk-platform

A ticketing backend for a small support team. Customers open tickets and reply on them, agents
work a shared queue, and admins manage accounts. A background worker flags tickets that missed
their first-response target and closes resolved tickets once the customer has gone quiet.

[![backend](https://github.com/emilbogdanov/helpdesk-platform/actions/workflows/backend.yml/badge.svg)](https://github.com/emilbogdanov/helpdesk-platform/actions/workflows/backend.yml)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

The React frontend is in progress; this release is the API, the worker and the admin CLI.

## Features

- Three roles: **customer** (sees only their own tickets), **agent** (works the queue) and
  **admin** (agent rights plus user management).
- Ticket lifecycle `open → in_progress → waiting_on_customer → resolved → closed`, enforced
  by the ticket itself. Agents can close spam straight from `open`; a customer's reply moves
  a ticket that was waiting on them back to `in_progress`, and reopens a resolved one.
- Public replies and internal notes on the same thread. Customers never see internal notes.
- First-response tracking: the first public reply from staff is timestamped, and the worker
  flags a ticket once it misses its target (urgent 1 h, high 4 h, normal 1 day, low 3 days).
- Auto-close of tickets that have stayed resolved for `HELPDESK_AUTO_CLOSE_AFTER_DAYS`.
- An audit entry for every change, with the actor (or the worker) and the before/after values.
- Queue filters by status, priority, assignee (`me`, `unassigned` or a user id) and requester,
  sorted by newest, oldest or recently updated, with cursor pagination.
- `Idempotency-Key` on ticket creation, so a client can retry a timed-out request without
  creating a duplicate.
- Optimistic locking: two agents editing the same ticket get a `409 concurrent_update` instead
  of one silently overwriting the other.
- Tickets and comments name the people on them (`{id, display_name, role}`), so a customer can
  see who replied without being able to look up accounts.
- Every error has the same shape, `{"detail", "code"}`, with a stable `code` to branch on.
- `helpdesk` CLI to bootstrap the first admin, reset a lost password and run the worker.

## Tech stack

Python 3.13, FastAPI, SQLAlchemy 2 (async) on asyncpg, PostgreSQL 17, Alembic, Redis 7,
PyJWT, argon2-cffi, pydantic-settings. Tooling: uv, ruff, mypy (strict), pytest with
testcontainers, pre-commit, GitHub Actions, Docker Compose.

## Quickstart

Needs Docker and Python. The middle command writes a random signing secret to `.env`; it works
in bash and in Windows cmd (use `python3` if that is what your system calls it).

```sh
git clone https://github.com/emilbogdanov/helpdesk-platform.git && cd helpdesk-platform
python -c "import secrets; print('HELPDESK_JWT_SECRET=' + secrets.token_urlsafe(48))" > .env
docker compose up --build
```

Compose starts Postgres and Redis, runs the migrations once, then starts the API on
<http://localhost:8000> and the worker. Interactive API docs are at
<http://localhost:8000/docs>.

Create the first admin (it prompts for the password):

```console
$ docker compose exec api helpdesk create-admin --email maria.ivanova@northwind.test --name "Maria Ivanova"
Password:
Repeat it:
created admin maria.ivanova@northwind.test (46b7e92c-7b05-45cb-b220-4db231fb8324)
```

## Usage

The examples use curl and jq, and a small helper that logs in and prints the access token:

```sh
token() {
  curl -s localhost:8000/auth/token -H 'Content-Type: application/json' \
    -d "{\"email\": \"$1\", \"password\": \"$2\"}" | jq -r .access_token
}
ADMIN=$(token maria.ivanova@northwind.test 'correct-horse-battery')
```

### Accounts

Anyone can sign up, and always gets the customer role:

```console
$ curl -s localhost:8000/auth/sign-up -H 'Content-Type: application/json' \
    -d '{"email": "petar.georgiev@acme.test", "display_name": "Petar Georgiev", "password": "winter-orchard-42"}' | jq
{
  "id": "910d416c-47ec-4903-b405-b0a88def47cc",
  "email": "petar.georgiev@acme.test",
  "display_name": "Petar Georgiev",
  "role": "customer",
  "is_active": true,
  "created_at": "2026-10-18T14:16:32.089101Z"
}
```

Staff accounts are created by an admin:

```console
$ curl -s localhost:8000/users -H 'Content-Type: application/json' -H "Authorization: Bearer $ADMIN" \
    -d '{"email": "elena.dimitrova@northwind.test", "display_name": "Elena Dimitrova", "role": "agent", "password": "quiet-harbour-17"}' | jq
{
  "id": "eaaeee17-af3c-4a5b-aa7c-fb571b282210",
  "email": "elena.dimitrova@northwind.test",
  "display_name": "Elena Dimitrova",
  "role": "agent",
  "is_active": true,
  "created_at": "2026-10-18T14:16:32.350141Z"
}
$ CUSTOMER=$(token petar.georgiev@acme.test winter-orchard-42)
$ AGENT=$(token elena.dimitrova@northwind.test quiet-harbour-17)
```

### Opening a ticket

```console
$ curl -s localhost:8000/tickets -H 'Content-Type: application/json' -H "Authorization: Bearer $CUSTOMER" \
    -H 'Idempotency-Key: 3b0f6c1e-0d6a-4a52-9f0e-checkout' \
    -d '{"subject": "Checkout returns 500 when the cart has a gift card", "description": "Every order with a gift card fails at the payment step since this morning. Orders without one go through.", "priority": "high"}' | jq
{
  "id": "5013d606-fa10-4d29-9850-c388206e56b8",
  "requester": {
    "id": "910d416c-47ec-4903-b405-b0a88def47cc",
    "display_name": "Petar Georgiev",
    "role": "customer"
  },
  "subject": "Checkout returns 500 when the cart has a gift card",
  "description": "Every order with a gift card fails at the payment step since this morning. Orders without one go through.",
  "priority": "high",
  "status": "open",
  "assignee": null,
  "created_at": "2026-10-18T14:16:32.634067Z",
  "updated_at": "2026-10-18T14:16:32.634067Z",
  "resolved_at": null,
  "closed_at": null,
  "first_responded_at": null,
  "sla_breached_at": null
}
```

Sending the same request again with the same key returns the ticket from the first attempt
(same `id`, same `created_at`). Reusing the key for a different ticket is rejected:

```json
{"detail": "idempotency key '3b0f6c1e-0d6a-4a52-9f0e-checkout' was already used for a different ticket", "code": "idempotency_key_reused"}
```

### Working it

```console
$ TICKET=5013d606-fa10-4d29-9850-c388206e56b8
$ curl -s -X POST localhost:8000/tickets/$TICKET/take -H "Authorization: Bearer $AGENT" | jq -c '{status, assignee: .assignee.display_name}'
{"status":"open","assignee":"Elena Dimitrova"}
$ curl -s -X PUT localhost:8000/tickets/$TICKET/status -H 'Content-Type: application/json' -H "Authorization: Bearer $AGENT" \
    -d '{"status": "in_progress"}' | jq -c '{status}'
{"status":"in_progress"}
$ curl -s localhost:8000/tickets/$TICKET/comments -H 'Content-Type: application/json' -H "Authorization: Bearer $AGENT" \
    -d '{"body": "Payment service logs show a null currency on gift card lines. Asked the payments team.", "visibility": "internal"}' > /dev/null
$ curl -s localhost:8000/tickets/$TICKET/comments -H 'Content-Type: application/json' -H "Authorization: Bearer $AGENT" \
    -d '{"body": "We can reproduce this and a fix is going out today. We will update this ticket when it is live."}' > /dev/null
```

The customer sees the public reply only, and the reply counts as the first response:

```console
$ curl -s localhost:8000/tickets/$TICKET/comments -H "Authorization: Bearer $CUSTOMER" | jq -c '.[] | {author: .author.display_name, visibility, body}'
{"author":"Elena Dimitrova","visibility":"public","body":"We can reproduce this and a fix is going out today. We will update this ticket when it is live."}
$ curl -s localhost:8000/tickets/$TICKET -H "Authorization: Bearer $CUSTOMER" | jq -c '{status, first_responded_at}'
{"status":"in_progress","first_responded_at":"2026-10-18T14:16:32.722955Z"}
```

Rules are enforced on the server, and each refusal has its own code:

```json
{"detail": "cannot move a ticket from in_progress to closed", "code": "invalid_status_transition"}
{"detail": "only agents and admins can take tickets", "code": "staff_only"}
{"detail": "only agents and admins can write internal notes", "code": "internal_note_not_allowed"}
```

A customer asking for someone else's ticket gets `404 ticket_not_found`, the same as for a
ticket that doesn't exist.

### The queue

Unassigned open tickets, oldest first, two per page:

```console
$ curl -s "localhost:8000/tickets?status=open&assignee=unassigned&sort=oldest&limit=2" \
    -H "Authorization: Bearer $AGENT" | jq '{items: [.items[] | {subject, priority}], next_cursor}'
{
  "items": [
    {
      "subject": "Invoice PDF shows last month's VAT rate",
      "priority": "normal"
    },
    {
      "subject": "Can't change the billing email on my account",
      "priority": "normal"
    }
  ],
  "next_cursor": "eyJzb3J0Ijoib2xkZXN0IiwiYXQiOiIyMDI2LTEwLTE4VDE0OjE2OjMyLjgyMTYwMSswMDowMCIsImlkIjoiY2VlOTM4ZWYtM2Y0MS00MDYwLTk3ZmItNjhlZGNiMDI5OWJhIn0"
}
```

Pass `next_cursor` back as `cursor` with the same filters to get the next page; it is `null`
on the last one. `status` and `priority` can be repeated (`?status=open&status=in_progress`).

### The worker

Every `HELPDESK_WORKER_INTERVAL_SECONDS` the worker runs two passes. Here an urgent ticket had
gone two hours without a reply, and the ticket above had been resolved for eight days:

```text
2026-10-18 14:16:41,285 INFO helpdesk.worker worker started; a pass every 0:01:00
2026-10-18 14:16:41,315 INFO helpdesk.worker job flag-overdue-first-responses: 1 ticket(s) changed
2026-10-18 14:16:41,323 INFO helpdesk.worker job close-resolved-tickets: 1 ticket(s) changed
```

Several worker replicas can run at once; a Redis lease lets only one of them run each pass.

### Audit trail

```console
$ docker compose exec db psql -U helpdesk -c "
    select coalesce(u.display_name, '(worker)') as actor, a.event_type,
           a.payload ->> 'previous' as previous, a.payload ->> 'current' as current
    from audit_entries a left join users u on u.id = a.actor_id
    where a.ticket_id = '$TICKET' order by a.id"
      actor      |    event_type    |  previous   |               current
-----------------+------------------+-------------+--------------------------------------
 Petar Georgiev  | ticket_opened    |             |
 Elena Dimitrova | assignee_changed |             | eaaeee17-af3c-4a5b-aa7c-fb571b282210
 Elena Dimitrova | status_changed   | open        | in_progress
 Elena Dimitrova | comment_added    |             |
 Elena Dimitrova | comment_added    |             |
 Elena Dimitrova | status_changed   | in_progress | resolved
 (worker)        | status_changed   | resolved    | closed
(7 rows)
```

### CLI

```console
$ docker compose exec api helpdesk --help
usage: helpdesk [-h] {create-admin,reset-password,worker} ...
```

`create-admin` and `reset-password` prompt for the password twice, or read it from
`HELPDESK_PASSWORD` when it is set (for scripts and CI).

## Project structure

```text
.
├── docker-compose.yml          db, redis, a one-shot migrate step, api, worker
├── .env.example                the one setting compose needs
└── backend/
    ├── Dockerfile              multi-stage, runs as a non-root user
    ├── pyproject.toml          dependencies and ruff, mypy, pytest config
    ├── migrations/             Alembic revisions
    ├── src/helpdesk/
    │   ├── domain/             Ticket, Comment and User with their rules; no I/O
    │   ├── application/        use cases, and the ports they need (repositories, unit of work,
    │   │                       hasher, token codec, audit log)
    │   ├── infrastructure/     SQLAlchemy tables and repositories, argon2, JWT, Redis lease
    │   ├── api/                FastAPI routes, request/response models, error mapping
    │   ├── worker.py           the polling loop and its lease
    │   ├── cli.py              the helpdesk command
    │   └── main.py             composition root: builds the API and the worker from settings
    └── tests/
        ├── unit/               domain and services against in-memory fakes
        ├── api/                HTTP behaviour, auth and permissions
        └── integration/        real Postgres and Redis via testcontainers
```

Dependencies point inward: `domain` imports nothing from the other layers, and `application`
knows only the ports it defines.

## Configuration

All settings are environment variables with the `HELPDESK_` prefix. Outside Docker they are
also read from `backend/.env` (see `backend/.env.example`).

| Variable | Default | Description |
| --- | --- | --- |
| `HELPDESK_DATABASE_URL` | required | `postgresql+asyncpg://` URL. Compose sets it. |
| `HELPDESK_REDIS_URL` | required | Redis URL for the worker lease. Compose sets it. |
| `HELPDESK_JWT_SECRET` | required | Signs access tokens; at least 32 characters. |
| `HELPDESK_ACCESS_TOKEN_TTL_MINUTES` | `15` | Lifetime of an access token. |
| `HELPDESK_WORKER_INTERVAL_SECONDS` | `60` | Time between worker passes. |
| `HELPDESK_AUTO_CLOSE_AFTER_DAYS` | `7` | How long a ticket stays resolved before it is closed. |
| `HELPDESK_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |
| `HELPDESK_PASSWORD` | unset | Read by `create-admin` and `reset-password` instead of prompting. |

## Running tests

```sh
cd backend
uv sync
uv run pytest
```

The integration tests start throwaway Postgres and Redis containers, so Docker must be
running. To skip them, run `uv run pytest -m "not integration"`. To reuse servers you already
have, set `HELPDESK_TEST_DATABASE_URL` and `HELPDESK_TEST_REDIS_URL`; the tests drop the
schema and flush Redis, so never point them at data you want to keep.

Linting and type checks, the same as CI and the pre-commit hook:

```sh
uv run ruff check && uv run ruff format --check && uv run mypy
```

To run the API on the host while developing, start only the backing services with
`docker compose up -d db redis`, copy `backend/.env.example` to `backend/.env`, then from
`backend/` run `uv run alembic upgrade head` and
`uv run uvicorn --factory helpdesk.main:app --reload`.

## Design notes

- **The ticket owns its rules.** Status transitions, "in progress needs an assignee", first
  response and reopen-on-reply all live on `Ticket`, which raises domain errors and records
  events. Services load, call one method and commit; the events become audit entries in the
  same transaction, so the trail can't drift from the data.
- **Concurrent writes fail loudly.** Tickets carry a version column, and a stale update is
  turned into `409 concurrent_update` rather than last-write-wins. Idempotent creates rely on a
  unique `(requester_id, idempotency_key)` constraint with `ON CONFLICT DO NOTHING` and a
  re-read, so two retries racing each other still produce one ticket.
- **Keyset pagination, backed by indexes.** The cursor encodes the sort column and id, and the
  query compares `(sort_column, id)` as a row value, so pages stay fast and stable while new
  tickets arrive. Every list view has a matching composite index, and the worker's lookups use
  partial indexes; integration tests run `EXPLAIN` to check the indexes are actually used.
- **One error table.** Domain and application errors map to an HTTP status and a code in
  `api/errors.py`. Anything not in it becomes a plain 500 with the traceback logged, instead of
  leaking details or being silently swallowed.
- **The worker is safe to scale and to interrupt.** A Redis lock with a TTL picks one runner
  per pass, each ticket is changed in its own transaction so one conflict doesn't undo the rest,
  and SIGTERM lets the current pass finish before the process exits.

## Limitations and roadmap

- No frontend yet. Next: a React + TypeScript app with a customer portal, the agent queue and
  admin screens, plus a stats endpoint for the admin dashboard.
- First-response targets count wall-clock time; there are no business hours or holidays.
- No refresh tokens, and access tokens are not revoked when a password is reset; they expire
  after `HELPDESK_ACCESS_TOKEN_TTL_MINUTES`. A deactivated account is locked out immediately.
- Password reset is admin-only through the CLI; there is no email flow.
- No notifications, attachments or full-text search. The audit log is written but not yet
  exposed through the API.

## License

MIT. See [LICENSE](LICENSE).
