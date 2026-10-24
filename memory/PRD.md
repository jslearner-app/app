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
- Backend (since 2026-10-24): ONE file /app/api/lambda_function.py (FastAPI app + Mangum `lambda_handler`, lifespan off, one-time init middleware): auth, clients, Textract pipeline, reconciliation, payout splitter (incl. LawPay exact fees), page caps + 80% low_page_alert, Stripe billing/webhooks, contact + emails. DB only via DATABASE_URL (+ DB_NAME or db in URL). /app/api also has requirements.txt, vercel.json (@vercel/python builds), .env.example, setup_stripe.py (one-time Stripe catalog).
- /app/backend is only an Emergent preview shim: server.py maps MONGO_URL -> DATABASE_URL and imports lambda_function.app (uvicorn --reload watches /app/backend only: restart backend after editing api/).
- Frontend /app/frontend = Vercel root (vercel.json, SPA rewrites). API base = process.env.NEXT_PUBLIC_API_URL (craco DefinePlugin; preview falls back to REACT_APP_BACKEND_URL).
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
- 2026-10-23: History "Needs review" filter (statements with reconciliation mismatch; combines with client filter)
- 2026-10-23: Review count badges (sidebar History + Needs review filter, live updates); landing SEO (meta/OG/Twitter, schema.org SoftwareApplication JSON-LD, keyword alt text, new hero copy, Use Cases H2/H3 section, robots.txt, fonts moved to preconnected link)
- 2026-10-24: LawPay in payout splitter (trust-compliant 4-line entry: Dr Trust Bank / Cr Client Trust Liability / Dr Card Processing Fees / Cr Operating Bank; default fee rate 3%). Pricing copy: Starter "Up to 200 parsed pages per month", Agency "Up to 1,000 parsed pages per month" (NOT enforced in backend yet). Core logic moved to standalone /app/api (ledgerstream_core + index.py + requirements.txt + vercel.json + .env.example, X-API-Key protected); backend imports it; DB via DATABASE_URL (fallback MONGO_URL); explicit CORS. Textract errors now return 424. Real AWS keys added by user but AWS org SCP denies textract:AnalyzeDocument
- 2026-10-24: Monthly page caps enforced (free 5 lifetime; Starter 200 / Agency 1,000 per UTC calendar month; atomic reserve + refund on failure). LawPay fees read line-by-line from the CSV fee column (no rate). Paid users switch plans via Stripe portal (subscription_update enabled; customer.subscription.updated webhook syncs plan)
- 2026-10-24: Low Page Alert banner (>=80% usage, charcoal/yellow, free->pricing, Starter->Stripe portal, Agency->sales mailto, session dismiss). App footer + commented third-party header/footer widget blocks (index.html, AppShell) with .support-widget-root safe area. Public /contact page (support@ / sales@ledgerstreamai.com)
- 2026-10-24: Contact form (dashboard bottom + /contact when signed in): name, account email (read-only), role, desk, message -> POST /api/contact (auth, server-side recipient, 5/hour rate limit, stored in contact_messages) -> Emergent managed Resend to support@/sales@ledgerstreamai.com
- 2026-10-24: Contact confirmation email to the sender's account email ("We got your message", desk-specific response time, reference id); failure is logged and doesn't block the desk email
- 2026-10-24: Production refactor for Vercel + AWS Lambda (single lambda_function.py, DATABASE_URL, NEXT_PUBLIC_API_URL, legacy backend modules/tests and old api/index.py + ledgerstream_core removed). Fixed Mangum warm-invocation bug (client closed after each call).
- Tested: iteration_1..7 (iteration_7: backend 21/21 via /app/backend_tests, frontend flows, Lambda warm invocations re-verified)
- 2026-10-24: Payout Variance Note: backend net_variance {file_net, calculated_net (first ledger debit line), difference, flagged on any cent difference} on create + recalculate; splitter shows amber note when flagged, green match note otherwise. Ledger footer label renamed to "Debit/credit difference".
- 2026-10-24: Textract: the AWS Organizations SCP denies textract:AnalyzeDocument for IAM user LedgerStream_Engine in every region (can't be fixed in code). The 424 response now explains the SCP block; the converter shows a persistent inline error banner; pages are not charged. Tested iteration_8 (backend 30/30, frontend pass)
- 2026-10-24: Textract connection check: POST /api/statements/engine/check (keys -> STS credentials -> AnalyzeDocument on a built-in reportlab sample statement -> parse + reconcile 3 rows; statuses ready/scp_blocked/iam_denied/invalid_keys/not_subscribed/unreachable/parse_mismatch; 30s cooldown; no pages charged; saved per user in textract_checks; last_check on GET /api/statements/engine). Dashboard converter card shows the steps + "Run check again".
- 2026-10-24: Variance in History: net_variance backfilled on startup for older payouts; History shows "Variance -$X" (amber) / "Matches file" (green) badges on payouts, Variance filter + count (/api/history?kind=variance, review-count.variance). Tested iteration_9 (backend 46/46, frontend pass)

## Backlog
- P0: Add AWS keys and verify live Textract parsing on real statements
- P1: Dashboard tab cards full width at 390px; splitter note explaining file net vs rate-based net difference
- P1: Async Textract (StartDocumentAnalysis + S3 + SNS -> /api/webhooks/textract) for very large PDFs; History delete confirmation
- P2: Team seats for Agency, client-level reporting

## Next tasks
Connect AWS keys; claim Stripe sandbox before going live.
