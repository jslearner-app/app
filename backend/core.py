from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import os
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import Request, HTTPException

from ledgerstream_core.db import connect

client, db = connect()

JWT_ALGORITHM = "HS256"
FREE_PAGE_LIMIT = 5
PAID_PLANS = {"starter", "agency"}
COOKIE_OPTS = dict(httponly=True, secure=True, samesite="none", path="/")


def now():
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": now() + timedelta(minutes=15), "type": "access"}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": now() + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def set_auth_cookies(response, user_id: str, email: str):
    response.set_cookie("access_token", create_access_token(user_id, email), max_age=900, **COOKIE_OPTS)
    response.set_cookie("refresh_token", create_refresh_token(user_id), max_age=604800, **COOKIE_OPTS)


def public_user(u: dict) -> dict:
    plan = u.get("plan", "free")
    return {
        "user_id": u["user_id"],
        "email": u["email"],
        "name": u.get("name", ""),
        "firm_name": u.get("firm_name", ""),
        "picture": u.get("picture"),
        "auth_provider": u.get("auth_provider", "password"),
        "plan": plan,
        "subscription_status": u.get("subscription_status", "active_subscriber" if plan in PAID_PLANS else "trial"),
        "pages_used": u.get("pages_used", 0),
        "page_limit": None if plan in PAID_PLANS else FREE_PAGE_LIMIT,
    }


def _as_utc(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _user_from_session(token: str):
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session or _as_utc(session["expires_at"]) < now():
        return None
    return await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0})


async def _user_from_jwt(token: str):
    try:
        payload = decode_token(token, "access")
    except jwt.InvalidTokenError:
        return None
    return await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})


async def get_current_user(request: Request) -> dict:
    bearer = request.headers.get("Authorization", "")
    bearer = bearer[7:] if bearer.startswith("Bearer ") else None
    user = None
    access = request.cookies.get("access_token") or bearer
    if access:
        user = await _user_from_jwt(access)
    session = request.cookies.get("session_token") or bearer
    if not user and session:
        user = await _user_from_session(session)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_owned_client(owner_id: str, client_id: str) -> dict:
    doc = await db.clients.find_one({"id": client_id, "owner_id": owner_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Client not found")
    return doc
