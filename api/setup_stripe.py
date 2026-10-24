



import os
import stripe

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

CATALOG = [
    {
        "emergent_product_id": "ledgerstream_starter",
        "name": "LedgerStream AI Starter",
        "tax_code": "txcd_10103001",
        "prices": [{"lookup_key": "starter_monthly", "amount": 9900, "currency": "usd", "interval": "month"}],
    },
    {
        "emergent_product_id": "ledgerstream_agency",
        "name": "LedgerStream AI Agency",
        "tax_code": "txcd_10103001",
        "prices": [{"lookup_key": "agency_monthly", "amount": 19900, "currency": "usd", "interval": "month"}],
    },
]


def get_or_create_product(entry):
    for p in stripe.Product.list(active=True).auto_paging_iter():
        if p.to_dict().get("metadata", {}).get("emergent_product_id") == entry["emergent_product_id"]:
            return p
    return stripe.Product.create(
        name=entry["name"], tax_code=entry.get("tax_code"),
        metadata={"managed_by": "emergent", "emergent_product_id": entry["emergent_product_id"]},
    )


for entry in CATALOG:
    product = get_or_create_product(entry)
    for p in entry["prices"]:
        existing = stripe.Price.list(lookup_keys=[p["lookup_key"]], active=True, limit=1).data
        if existing and (existing[0].unit_amount != p["amount"] or existing[0].currency != p["currency"]):
            stripe.Price.modify(existing[0].id, active=False)
            existing = []
        if not existing:
            kwargs = dict(product=product.id, unit_amount=p["amount"], currency=p["currency"],
                          lookup_key=p["lookup_key"], transfer_lookup_key=True)
            if p.get("interval"):
                kwargs["recurring"] = {"interval": p["interval"]}
            stripe.Price.create(**kwargs)
    print("ok", entry["name"])
