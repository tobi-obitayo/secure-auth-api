# Auth API

> **Learning project.** A small FastAPI service for practicing user registration, password hashing, login tokens, and a limit on failed sign-in attempts.

This is one file of API code plus tests. It is here to learn the shape of an auth flow, and to read alongside the interactive docs at `/docs`. Keep it on your machine while you experiment.

## What you can practice

- Create an account and store a bcrypt hash instead of a password
- Log in and receive a short-lived bearer token
- Call a protected route with that token
- Watch how failed logins are counted for an IP address

## Routes

| Method | Path | What happens |
| --- | --- | --- |
| `GET` | `/health` | Returns `{ "status": "ok" }` |
| `POST` | `/register` | Creates a user (`201`), or `409` if that username is taken |
| `POST` | `/login` | Returns a bearer token, or `401` when the username or password is wrong |
| `GET` | `/me` | Returns the username stored in a valid token |

After the server is running, open [http://localhost:8000/docs](http://localhost:8000/docs). FastAPI builds that page from these routes.

## Run it locally

You need Python 3.9 or newer.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Set your own signing secret before you use this beyond a local exercise:

```bash
export JWT_SECRET="replace-this-with-at-least-32-random-bytes"
```

If `JWT_SECRET` is unset, the app starts with a short development default so you can try the routes immediately.

## Try a request

Register:

```bash
curl -s -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"ada","password":"correct-horse"}'
```

Log in, then call `/me` with the token from the login response:

```bash
curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"ada","password":"correct-horse"}'
```

```bash
curl -s http://localhost:8000/me \
  -H "Authorization: Bearer PASTE_TOKEN_HERE"
```

Usernames must be 3 to 50 characters. Passwords must be 8 to 72 characters.

## Tests

With the virtual environment active:

```bash
pytest
```

`test_main.py` covers the health check, registration, duplicate usernames, login plus `/me`, and the failed-login limit.

## Ideas in the code

**Password hashes.** `register` stores a bcrypt hash. The SQLite file never keeps the password itself.

**One error for both failures.** Login returns the same `401` when the username is missing and when the password is wrong.

**A stand-in hash.** If the username does not exist, login still runs bcrypt against a dummy hash so the response takes a similar amount of time.

**Tokens.** A successful login returns a JWT that expires after 15 minutes. `/me` reads the `Authorization: Bearer` header and returns the username in the token.

**Failed-login limit.** Recent failure times are kept in memory, per IP address. `check_rate_limit` is written to answer with `429` after 5 failures inside 60 seconds.

## Project layout

```text
main.py            the API
test_main.py       pytest checks
requirements.txt   pinned dependencies
```

SQLite creates `users.db` the first time the app starts. That file stays on your machine. `.gitignore` keeps the database, the virtual environment, and `.env` out of git.

## Scope of this exercise

Accounts live in a local SQLite file. The failure counter lives in process memory, so it resets when the server restarts and it is not shared across multiple processes. Set `JWT_SECRET` yourself when you move past the learning setup.
