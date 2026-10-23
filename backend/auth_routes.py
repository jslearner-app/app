import logging
import secrets
from datetime import timedelta

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, now, new_id, hash_password, verify_password, set_auth_cookies, decode_token,
    create_access_token, public_user, get_current_user, COOKIE_OPTS,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    firm_name: str = Field(default="", max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleSessionIn(BaseModel):
    session_id: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


def new_user_doc(email: str, name: str, provider: str, **extra) -> dict:
    return {
        "user_id": new_id("user"), "email": email, "name": name, "auth_provider": provider,
        "plan": "free", "subscription_status": "trial", "pages_used": 0, "created_at": now(), **extra,
    }


@router.post("/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    doc = new_user_doc(email, body.name.strip(), "password",
                       firm_name=body.firm_name.strip(), password_hash=hash_password(body.password))
    await db.users.insert_one(doc)
    set_auth_cookies(response, doc["user_id"], email)
    return public_user(doc)


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.lower()
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    identifier = f"{forwarded or (request.client.host if request.client else 'unknown')}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if attempt and attempt.get("locked_until"):
        locked_until = attempt["locked_until"]
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=now().tzinfo)
        if locked_until > now():
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        count = (attempt or {}).get("count", 0) + 1
        update = {"count": count, "updated_at": now()}
        if count >= MAX_ATTEMPTS:
            update = {"count": 0, "locked_until": now() + timedelta(minutes=LOCKOUT_MINUTES)}
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    await db.login_attempts.delete_one({"identifier": identifier})
    set_auth_cookies(response, user["user_id"], email)
    return public_user(user)


@router.post("/google/session")
async def google_session(body: GoogleSessionIn, response: Response):
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": body.session_id})
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Google sign-in failed")
    data = r.json()
    email = data["email"].lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"picture": data.get("picture")}})
        user["picture"] = data.get("picture")
    else:
        user = new_user_doc(email, data.get("name", ""), "google", picture=data.get("picture"))
        await db.users.insert_one(user)
        user.pop("_id", None)
    await db.user_sessions.insert_one({
        "user_id": user["user_id"], "session_token": data["session_token"],
        "expires_at": now() + timedelta(days=7), "created_at": now(),
    })
    response.set_cookie("session_token", data["session_token"], max_age=604800, **COOKIE_OPTS)
    return public_user(user)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(token, "refresh")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    response.set_cookie("access_token", create_access_token(user["user_id"], user["email"]), max_age=900, **COOKIE_OPTS)
    return {"ok": True}


@router.post("/logout")
async def logout(request: Request, response: Response):
    session = request.cookies.get("session_token")
    if session:
        await db.user_sessions.delete_one({"session_token": session})
    for name in ("access_token", "refresh_token", "session_token"):
        response.delete_cookie(name, path="/", secure=True, samesite="none")
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password(body: ForgotIn, request: Request):
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token, "user_id": user["user_id"], "used": False,
            "expires_at": now() + timedelta(hours=1),
        })
        logger.info("Password reset link: %s/reset-password?token=%s", request.headers.get("origin", ""), token)
    return {"ok": True}


@router.post("/reset-password")
async def reset_password(body: ResetIn):
    rec = await db.password_reset_tokens.find_one({"token": body.token, "used": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=400, detail="Invalid or used reset token")
    exp = rec["expires_at"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=now().tzinfo)
    if exp < now():
        raise HTTPException(status_code=400, detail="Reset token expired")
    await db.users.update_one({"user_id": rec["user_id"]}, {"$set": {"password_hash": hash_password(body.password)}})
    await db.password_reset_tokens.update_one({"token": body.token}, {"$set": {"used": True}})
    return {"ok": True}
