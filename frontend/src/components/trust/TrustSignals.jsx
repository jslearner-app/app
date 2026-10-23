import { Lock, Quote, ServerCog, ShieldCheck, Timer, CreditCard } from "lucide-react";

const PLATFORM_BADGES = [
  { id: "shopify", title: "Shopify compatible", sub: "Direct CSV Ingestion Pipeline", logo: "/logos/shopify.svg" },
  { id: "doordash", title: "DoorDash Data Partner", sub: "Automated Fee & Commission Parsing", logo: "/logos/doordash.svg" },
  { id: "ubereats", title: "UberEats Ready", sub: "Instant Settlement Breakdown", logo: "/logos/ubereats.svg" },
  { id: "toast", title: "Toast Ecosystem", sub: "POS Daily Clearing Reconciliation", logo: "/logos/toast.svg" },
];

const REVIEWS = [
  {
    id: "sarah",
    quote: "LedgerStream AI turned a multi-year restaurant cleanup backlog that usually takes our team two full weeks into a simple 10-minute file drop. The Toast payout splits balanced down to the exact penny on the first try.",
    name: "Sarah M.",
    role: "CPA & Founder of Apex Bookkeeping Firm",
    initials: "SM",
  },
  {
    id: "david",
    quote: "As a solo virtual bookkeeper handling 8 Shopify clients, manual e-commerce settlement adjustments used to ruin my weekends. This app entirely automates my workflow.",
    name: "David K.",
    role: "Freelance E-commerce Bookkeeper",
    initials: "DK",
  },
];

const SECURITY = [
  { icon: ServerCog, title: "AWS Isolated Parsing", sub: "Each statement is processed in an isolated job" },
  { icon: Lock, title: "256-bit Document Isolation", sub: "Encrypted in transit and at rest" },
  { icon: Timer, title: "Auto-delete in 1 hour", sub: "Source files are never retained" },
  { icon: CreditCard, title: "Stripe Verified", sub: "PCI-compliant subscription billing" },
];

export const TrustBadgesRow = ({ compact = false }) => (
  <div className={`grid grid-cols-2 lg:grid-cols-4 ${compact ? "gap-3" : "gap-4 sm:gap-6"}`} data-testid="platform-trust-badges">
    {PLATFORM_BADGES.map((b, i) => (
      <div
        key={b.id}
        data-testid={`trust-badge-${b.id}`}
        style={{ animationDelay: `${i * 80}ms` }}
        className={`reveal group surface ${compact ? "p-4" : "p-5 sm:p-6"} hover:border-emerald-500/40 transition-colors duration-200`}
      >
        <img src={b.logo} alt={`${b.title} logo`} width="28" height="28" loading="lazy" className="h-7 w-7 opacity-80 group-hover:opacity-100 transition-opacity" />
        <div className="mt-4 font-display font-semibold text-sm sm:text-base text-slate-100">{b.title}</div>
        <div className="mt-1 text-xs sm:text-sm text-slate-400">{b.sub}</div>
      </div>
    ))}
  </div>
);

export const CaseStudyReviews = ({ compact = false }) => (
  <div className="grid gap-4 sm:gap-6 md:grid-cols-2" data-testid="case-study-reviews">
    {REVIEWS.map((r, i) => (
      <figure
        key={r.id}
        data-testid={`review-card-${r.id}`}
        style={{ animationDelay: `${120 + i * 100}ms` }}
        className={`reveal surface relative ${compact ? "p-5" : "p-6 sm:p-8"} flex flex-col`}
      >
        <Quote className="h-6 w-6 text-emerald-500/70" />
        <blockquote className={`mt-4 text-slate-200 leading-relaxed ${compact ? "text-sm" : "text-base sm:text-lg"}`}>“{r.quote}”</blockquote>
        <figcaption className="mt-6 pt-5 border-t border-slate-800 flex items-center gap-3">
          <span className="h-10 w-10 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-sm font-semibold flex items-center justify-center">{r.initials}</span>
          <span>
            <span className="block font-semibold text-slate-100 text-sm">{r.name}</span>
            <span className="block text-xs text-slate-400">{r.role}</span>
          </span>
        </figcaption>
      </figure>
    ))}
  </div>
);

export const SecurityStrip = () => (
  <div className="grid grid-cols-2 lg:grid-cols-4 gap-px rounded-xl overflow-hidden border border-slate-800 bg-slate-800" data-testid="security-certifications">
    {SECURITY.map((s) => (
      <div key={s.title} className="bg-[#0d1630] p-5 sm:p-6">
        <s.icon className="h-5 w-5 text-emerald-400" />
        <div className="mt-3 text-sm font-semibold text-slate-100">{s.title}</div>
        <div className="mt-1 text-xs text-slate-400">{s.sub}</div>
      </div>
    ))}
  </div>
);

export const IsolationBadge = ({ testId = "secure-isolation-badge" }) => (
  <div className="mt-3 flex items-start sm:items-center gap-2 text-xs text-slate-400" data-testid={testId}>
    <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" />
    <span>
      <Lock className="inline h-3 w-3 mr-1 -mt-0.5 text-emerald-400" />
      <span className="text-slate-200 font-medium">Secure 256-bit Document Isolation.</span> Your files are automatically deleted after 1 hour.
    </span>
  </div>
);

const CHECKOUT_BADGES = [
  { id: "quickbooks", title: "QuickBooks Certified", logo: "/logos/quickbooks.svg" },
  { id: "xero", title: "Xero Approved", logo: "/logos/xero.svg" },
  { id: "stripe", title: "Stripe Secure Checkout", logo: "/logos/stripe.svg" },
];

export const CheckoutTrustBadges = () => (
  <div className="flex flex-col gap-3" data-testid="checkout-trust-badges">
    {CHECKOUT_BADGES.map((b) => (
      <div key={b.id} data-testid={`checkout-badge-${b.id}`} className="flex items-center gap-3 rounded-lg border border-slate-700/80 bg-slate-900/80 px-3 py-2.5">
        <img src={b.logo} alt={`${b.title} logo`} width="20" height="20" loading="lazy" className="h-5 w-5" />
        <span className="text-xs font-medium text-slate-200">{b.title}</span>
      </div>
    ))}
  </div>
);
