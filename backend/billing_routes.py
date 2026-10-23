import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core import db, now, get_current_user, public_user, PAID_PLANS

router = APIRouter(prefix="/api", tags=["billing"])
logger = logging.getLogger(__name__)
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
TAX_MODE = "full"
PLAN_LOOKUP = {"starter": "starter_monthly", "agency": "agency_monthly"}


class CheckoutIn(BaseModel):
    plan: str
    origin_url: str


class PortalIn(BaseModel):
    origin_url: str


async def _activate(session_id: str, session=None):
    """Idempotently mark a transaction paid and upgrade the user's plan."""
    res = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid",
                  "stripe_subscription_id": getattr(session, "subscription", None) if session else None,
                  "stripe_customer_id": getattr(session, "customer", None) if session else None,
                  "updated_at": now()}},
    )
    if res.modified_count == 0:
        return
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    await db.users.update_one({"user_id": tx["user_id"]}, {"$set": {
        "plan": tx["plan"], "subscription_status": "active_subscriber", "stripe_customer_id": tx.get("stripe_customer_id"),
        "stripe_subscription_id": tx.get("stripe_subscription_id"), "plan_updated_at": now(),
    }})


def _create_session(kwargs):
    if TAX_MODE == "full":
        try:
            return stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError as e:
            msg = (e.user_message or str(e)).lower()
            if "managed payments" not in msg and "ineligible" not in msg and "managed_payments" not in msg:
                raise
            logger.warning("Managed payments unavailable, falling back to automatic tax: %s", msg)
    return stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")


@router.get("/billing/summary")
async def billing_summary(user: dict = Depends(get_current_user)):
    return {**public_user(user), "has_portal": bool(user.get("stripe_customer_id"))}


@router.post("/payments/checkout")
async def create_checkout(body: CheckoutIn, user: dict = Depends(get_current_user)):
    lookup_key = PLAN_LOOKUP.get(body.plan)
    if not lookup_key:
        raise HTTPException(status_code=400, detail="Unknown plan")
    prices = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1).data
    if not prices:
        raise HTTPException(status_code=500, detail=f"Price not found: {lookup_key}")
    price = prices[0]
    origin = body.origin_url.rstrip("/")
    kwargs = dict(
        line_items=[{"price": price.id, "quantity": 1}],
        mode="subscription",
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/payment/cancel",
        customer_email=user["email"],
        metadata={"user_id": user["user_id"], "plan": body.plan, "lookup_key": lookup_key},
    )
    try:
        session = _create_session(kwargs)
    except stripe.error.StripeError as e:
        logger.exception("Stripe checkout failed")
        raise HTTPException(status_code=502, detail=e.user_message or "Payment provider error")
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["user_id"], "plan": body.plan, "lookup_key": lookup_key,
        "amount": float(price.unit_amount or 0) / 100.0, "currency": price.currency,
        "status": "initiated", "payment_status": "pending", "created_at": now(), "updated_at": now(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


@router.get("/payments/status/{session_id}")
async def payment_status(session_id: str):
    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await _activate(session_id, s)
                record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"],
            "payment_status": record["payment_status"], "plan": record.get("plan")}


@router.post("/billing/portal")
async def billing_portal(body: PortalIn, user: dict = Depends(get_current_user)):
    customer = user.get("stripe_customer_id")
    if not customer or user.get("plan") not in PAID_PLANS:
        raise HTTPException(status_code=400, detail="No active subscription to manage yet")
    try:
        if not stripe.billing_portal.Configuration.list(limit=1).data:
            stripe.billing_portal.Configuration.create(
                business_profile={"headline": "LedgerStream AI billing"},
                features={
                    "invoice_history": {"enabled": True},
                    "payment_method_update": {"enabled": True},
                    "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
                },
            )
        session = stripe.billing_portal.Session.create(customer=customer, return_url=f"{body.origin_url.rstrip('/')}/billing")
    except stripe.error.StripeError as e:
        logger.exception("Stripe portal failed")
        raise HTTPException(status_code=502, detail=e.user_message or "Could not open the billing portal")
    return {"url": session.url}


@router.post("/webhooks/stripe")
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), STRIPE_WEBHOOK_SECRET)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if obj.get("payment_status") == "paid" or obj.get("status") == "complete":
            await _activate(obj["id"], stripe.checkout.Session.construct_from(obj, stripe.api_key))
    elif t in ("checkout.session.async_payment_failed", "checkout.session.expired"):
        status = "failed" if t.endswith("failed") else "expired"
        await db.payment_transactions.update_one({"session_id": obj["id"]},
                                                 {"$set": {"status": status, "payment_status": status, "updated_at": now()}})
    elif t == "customer.subscription.deleted":
        await db.users.update_one(
            {"$or": [{"stripe_subscription_id": obj["id"]}, {"stripe_customer_id": obj.get("customer")}]},
            {"$set": {"plan": "free", "subscription_status": "trial", "plan_updated_at": now()}},
        )
    logger.info("Stripe webhook processed: %s", t)
    return {"status": "ok"}
