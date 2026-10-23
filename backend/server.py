import logging
import os

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core import db, client, now, new_id, hash_password, verify_password
from auth_routes import router as auth_router
from workspace_routes import router as workspace_router
from billing_routes import router as billing_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="LedgerStream AI")
app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(billing_router)


@app.get("/api/")
async def root():
    return {"service": "LedgerStream AI", "status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ["CORS_ORIGINS"].split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

DEMO_CLIENTS = [
    {"name": "The Burger Shack", "industry": "Restaurant", "platforms": ["toast", "doordash", "ubereats"]},
    {"name": "Downtown Boutique", "industry": "Retail / E-commerce", "platforms": ["shopify", "stripe"]},
]


async def seed_demo_user():
    email, password = os.environ["DEMO_EMAIL"].lower(), os.environ["DEMO_PASSWORD"]
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing is None:
        user_id = new_id("user")
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": "Demo Bookkeeper", "firm_name": "Demo Bookkeeping Co.",
            "auth_provider": "password", "password_hash": hash_password(password),
            "plan": "free", "subscription_status": "trial", "pages_used": 0, "created_at": now(),
        })
        for c in DEMO_CLIENTS:
            await db.clients.insert_one({
                "id": new_id("cli"), "owner_id": user_id, "contact_email": "", "notes": "",
                **c, "created_at": now().isoformat(),
            })
    elif not existing.get("password_hash") or not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token")
    await db.login_attempts.create_index("identifier")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.clients.create_index([("owner_id", 1), ("created_at", -1)])
    await db.statements.create_index([("owner_id", 1), ("created_at", -1)])
    await db.payouts.create_index([("owner_id", 1), ("created_at", -1)])
    await db.payment_transactions.create_index("session_id", unique=True)
    await seed_demo_user()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
