import os
from datetime import timedelta
from html import escape
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from core import db, now, new_id, get_current_user
from emailer import EMAIL_FROM_NAME, send_email

router = APIRouter(prefix="/api", tags=["contact"])

DESKS = {
    "support": ("General Support & Engineering", "SUPPORT_DESK_EMAIL"),
    "sales": ("Enterprise & Firm Sales", "SALES_DESK_EMAIL"),
}
ROLES = {
    "firm_owner": "Firm owner / CPA",
    "staff_bookkeeper": "Staff bookkeeper",
    "freelance_bookkeeper": "Freelance bookkeeper",
    "controller": "Controller / finance lead",
    "other": "Other",
}
HOURLY_LIMIT = 5


class ContactIn(BaseModel):
    desk: Literal["support", "sales"]
    name: str = Field(min_length=1, max_length=120)
    role: Literal["firm_owner", "staff_bookkeeper", "freelance_bookkeeper", "controller", "other"]
    message: str = Field(min_length=10, max_length=4000)

    @field_validator("name", "message", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


def _render(desk_label: str, name: str, email: str, role: str, firm: str, plan: str, message: str) -> str:
    rows = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#64748b;font-size:13px">{k}</td>'
        f'<td style="padding:4px 0;font-size:13px;color:#0f172a">{v}</td></tr>'
        for k, v in [("Name", escape(name)), ("Account email", escape(email)), ("Role", escape(role)),
                     ("Firm", escape(firm or "-")), ("Plan", escape(plan))]
    )
    body = escape(message).replace("\n", "<br>")
    return (
        '<table role="presentation" width="100%" style="font-family:Arial,sans-serif;background:#f8fafc">'
        '<tr><td style="padding:24px">'
        f'<h2 style="margin:0 0 4px;font-size:18px;color:#0b132b">New {escape(desk_label)} message</h2>'
        '<p style="margin:0 0 16px;font-size:13px;color:#64748b">Submitted through the in-app contact form.</p>'
        f'<table role="presentation">{rows}</table>'
        '<div style="margin-top:16px;padding:16px;background:#ffffff;border:1px solid #e2e8f0;'
        f'border-radius:8px;font-size:14px;line-height:1.5;color:#0f172a">{body}</div>'
        f'<p style="margin-top:16px;font-size:12px;color:#94a3b8">Sent by {escape(EMAIL_FROM_NAME)}. '
        'Reply to the account email above to respond.</p>'
        '</td></tr></table>'
    )


@router.post("/contact")
async def submit_contact(body: ContactIn, user: dict = Depends(get_current_user)):
    since = (now() - timedelta(hours=1)).isoformat()
    recent = await db.contact_messages.count_documents(
        {"user_id": user["user_id"], "created_at": {"$gte": since}, "status": {"$ne": "failed"}})
    if recent >= HOURLY_LIMIT:
        raise HTTPException(status_code=429, detail="You've sent several messages recently. Please try again in an hour.")
    desk_label, env_key = DESKS[body.desk]
    role = ROLES[body.role]
    record = {
        "id": new_id("msg"), "user_id": user["user_id"], "email": user["email"], "desk": body.desk,
        "name": body.name.strip(), "role": body.role, "message": body.message.strip(),
        "status": "pending", "created_at": now().isoformat(),
    }
    await db.contact_messages.insert_one(record)
    subject = f"[{EMAIL_FROM_NAME}] {desk_label} message from {body.name.strip()}"
    html = _render(desk_label, record["name"], user["email"], role, user.get("firm_name", ""),
                   user.get("plan", "free"), record["message"])
    try:
        email_id = await send_email(to=os.environ[env_key], subject=subject, html=html)
    except HTTPException:
        await db.contact_messages.update_one({"id": record["id"]}, {"$set": {"status": "failed"}})
        raise
    await db.contact_messages.update_one({"id": record["id"]}, {"$set": {"status": "sent", "email_id": email_id}})
    return {"ok": True, "id": record["id"], "desk": body.desk}
