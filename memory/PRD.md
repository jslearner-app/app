# LedgerStream AI — PRD

## Original problem statement (customer's words, condensed headings kept)
Build a production-ready B2B web application for bookkeeping firms called "LedgerStream AI". The application must combine two core modules into a single, seamless user dashboard: a "Bank Statement Converter" and a "Merchant Payout Splitter."
1. User Authentication & Multi-Tenant Structure: secure sign-up/login; sidebar "Dashboard", "Client Accounts", "History", "Billing"; client profiles (e.g. "The Burger Shack", "Downtown Boutique").
2. Tab A Bank Statement Converter: drag-and-drop multi-page PDF uploader, client dropdown, loading text "Parsing statement structure via AWS Textract...", data grid Date, Description, Reference/Check #, Withdrawals, Deposits, Balance; button "Export to Accounting Excel/CSV".
   Tab B Merchant Payout Splitter: upload Toast/DoorDash/UberEats/Shopify/Stripe statements; "Platform Commission Rate %" default 30%; balanced matrix Debit Bank Clearing (Net), Debit Delivery Commissions Expense, Credit Gross Sales Revenue; Total Debits = Total Credits with green badge "Balanced: Ready to Export"; button "Download QuickBooks Journal Entry CSV".
3. Backend: Python pipeline; PDF upload connects to Amazon Textract Tables API via secure webhook; parse Textract JSON with Pandas; ledger math rounds exactly to 2 decimals.
4. Billing: Stripe Customer Portal; free trial limit 5 pages then pricing matrix ($99 Starter, $199 Agency).
Dark navy / charcoal / emerald palette. Trust Signals on landing + onboarding dashboard (platform badges with subtext; reviews by Sarah M. and David K. verbatim). Placement A under upload zones: "Secure 256-bit Document Isolation. Your files are automatically deleted after 1 hour." Placement B next to $99 Starter checkout: QuickBooks Certified, Xero Approved, Stripe Secure Checkout.
Follow-up request: stop using simulated placeholders; real boto3 Textract analyze_document with TABLES; env AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION; official stripe library; webhook /api/webhooks/stripe for checkout.session.completed and customer.subscription.deleted; user status trial -> active_subscriber; STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET.

## User choices
JWT email/password + Google sign-in; Textract keys added later; Stripe claimable sandbox; payout CSV auto-detect gross/net; trial = 5 PDF pages per user account.

## Architecture
- Backend FastAPI: core.py (db, JWT + Emergent session auth), auth_routes.py, workspace_routes.py (clients, statements, Textract HMAC webhook, payouts, history, dashboard), billing_routes.py (Stripe checkout/status/portal/webhooks), textract_pipeline.py (boto3 analyze_document TABLES per page -> Blocks -> pandas), ledger_engine.py (Decimal ROUND_HALF_UP ledger, QBO CSV), setup_stripe.py (catalog starter_monthly/agency_monthly).
- Data scoped by owner_id (user_id). Raw files processed in memory, never stored.
- Frontend React + shadcn, Plus Jakarta Sans / IBM Plex Sans / JetBrains Mono.

## Personas
CPA firm founders cleaning restaurant backlogs; solo virtual e-commerce bookkeepers.

## Implemented (2026-10-22/23)
- Landing page with trust badges, reviews, security strip, pricing (Placement B)
- Auth: register/login/logout/refresh, brute-force lockout, Google login
- Client CRUD with stats; History with filters, re-export, delete
- Converter: real Textract pipeline (503 until AWS keys set), grid with filter/sort/edit, CSV/XLSX export, trial gate (402 -> /pricing)
- Splitter: CSV detection for 5 platforms, balanced ledger, live recalc, QBO CSV, sample CSVs
- Billing: Stripe sandbox checkout, status polling, Customer Portal, webhooks at /api/webhooks/stripe and /api/stripe/webhook; subscription_status trial <-> active_subscriber
- 2026-10-23: Statement reconciliation check (opening + deposits - withdrawals vs printed running/closing balance; mismatched rows highlighted; recomputed on row edits). AWS keys requested via secure card; user skipped, so Textract is still not connected
- 2026-10-23: History shows a reconciliation badge per statement (Reconciled / Needs review / No balance column)
- Tested: iteration_1 (backend 23/23; frontend flows incl. real Stripe test checkout)

## Backlog
- P0: Add AWS keys and verify live Textract parsing on real statements
- P1: Async Textract (StartDocumentAnalysis + S3 + SNS -> /api/webhooks/textract) for very large PDFs; History delete confirmation
- P2: Team seats for Agency, client-level reporting

## Next tasks
Connect AWS keys; claim Stripe sandbox before going live.
