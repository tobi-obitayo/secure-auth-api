import time
from collections import defaultdict, deque
from urllib import request
from fastapi import Request
import os
from datetime import datetime, timedelta, timezone
import token
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import sqlite3
import bcrypt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()
DB_PATH = "users.db"

# ---------- Database helpers ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us read columns by name
    return conn

def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

init_db()

# A valid bcrypt hash of a throwaway password. Used to keep login timing
# consistent when the username doesn't exist.
DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password",
bcrypt.gensalt()).decode("utf-8")


# ---------- JWT configuration ----------
# In real life this comes from an environment variable, never from source code.
SECRET_KEY = os.environ.get("JWT_SECRET", "dev-only-change-me")
ALGORITHM = "HS256"
TOKEN_MINUTES = 15
bearer_scheme = HTTPBearer()
def create_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username, # who this token is for
        "iat": now, # issued at
        "exp": now + timedelta(minutes=TOKEN_MINUTES), # expires at
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),) -> str:
    try:
        payload = jwt.decode(
        credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM]
    )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]

# ---------- Rate limiting ----------
MAX_FAILED_ATTEMPTS = 5
WINDOW_SECONDS = 60

# Maps an IP address to a deque of failure timestamps.
# defaultdict(deque) creates an empty deque the first time we see a new IP.

failed_attempts = defaultdict(deque)

def check_rate_limit(ip: str):
    now = time.time()
    attempts = failed_attempts[ip]
    
    # Drop failures that fell outside the 60-second window
    while attempts and now - attempts[0] > WINDOW_SECONDS:
        attempts.popleft()
        if len(attempts) >= MAX_FAILED_ATTEMPTS:
            retry_after = int(WINDOW_SECONDS - (now - attempts[0])) + 1
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )
       
def record_failure(ip: str):
    failed_attempts[ip].append(time.time())

# ---------- Request shape ----------
class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)

# ---------- Routes ----------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/register", status_code=201)
def register(creds: Credentials):
    hashed = bcrypt.hashpw(creds.password.encode("utf-8"), bcrypt.gensalt())
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (creds.username, hashed.decode("utf-8")),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already taken")
    finally:
        conn.close()
    return {"message": "User created"}

@app.post("/login")
def login(creds: Credentials, request: Request):
    ip = request.client.host
    # Step 1: rate limit BEFORE doing any expensive work
    check_rate_limit(ip)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT username, password_hash FROM users WHERE username = ?",
            (creds.username,),
        ).fetchone()
    finally:
        conn.close()
        
    # 2. Pick a hash to check against (the real one, or the dummy)
    stored_hash = row["password_hash"] if row else DUMMY_HASH
   
    # 3. Always run the bcrypt comparison
    password_ok = bcrypt.checkpw(
        creds.password.encode("utf-8"), stored_hash.encode("utf-8")
    )
    
    # 4. Same error for 'no such user' and 'wrong password'
    if row is None or not password_ok:
        record_failure(ip) # count this against the IP
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(creds.username)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me")
def me(username: str = Depends(get_current_user)):
    return {"username": username}