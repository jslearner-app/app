"""Helper: python set_demo_state.py <free|starter|agency> <pages>  (sets demo user usage in Mongo; 'reset' restores defaults)."""
import sys
from datetime import datetime, timezone
from dotenv import dotenv_values
from pymongo import MongoClient

env = dotenv_values("/app/backend/.env")
db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
plan = sys.argv[1]
q = {"email": "demo@ledgerstream.ai"}
if plan in ("reset", "free"):
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    db.users.update_one(q, {"$set": {"plan": "free", "subscription_status": "trial", "pages_used": pages},
                            "$unset": {"usage_period": "", "period_pages": ""}})
else:
    db.users.update_one(q, {"$set": {"plan": plan, "subscription_status": "active_subscriber", "pages_used": 0,
                                     "usage_period": datetime.now(timezone.utc).strftime("%Y-%m"),
                                     "period_pages": int(sys.argv[2])}})
print(db.users.find_one(q, {"_id": 0, "plan": 1, "pages_used": 1, "usage_period": 1, "period_pages": 1}))
