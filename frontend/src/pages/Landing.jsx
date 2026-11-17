import React, { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, FileSpreadsheet, Scale } from "lucide-react";
import { Brand } from "@/components/common/Brand";
import { useAuth } from "@/context/AuthContext";
import { TrustBadgesRow, CaseStudyReviews, SecurityStrip } from "@/components/trust/TrustSignals";
import { PricingMatrix } from "@/components/billing/PricingMatrix";
import { HeroPreview } from "@/components/landing/HeroPreview";
import { UseCases } from "@/components/landing/UseCases";

const PAGE_TITLE = "LedgerStream AI | The Financial Ingestion Hub for Modern Bookkeepers";

const Section = ({ id, eyebrow, title, sub, children, testId }) => (
  <section id={id} className="px-5 sm:px-8 lg:px-16 py-16 sm:py-24 max-w-7xl mx-auto" data-testid={testId}>
    <div className="max-w-2xl mb-10 sm:mb-14">
      <div className="eyebrow mb-3">{eyebrow}</div>
      <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight text-slate-50">{title}</h2>
      {sub && <p className="mt-3 text-base md:text-lg text-slate-400">{sub}</p>}
    </div>
    {children}
  </section>
);

const MODULES = [
  { icon: FileSpreadsheet, title: "Bank Statement Converter", text: "Drop multi-page PDF statements. Google Document AI bank statement parsing and a Pandas pipeline return a flat, editable ledger.", cols: ["Date", "Description", "Reference/Check #", "Withdrawals", "Deposits", "Balance"], out: "Excel / CSV ledger for backlogs" },
  { icon: Scale, title: "Merchant Payout Splitter", text: "Upload Toast, DoorDash, UberEats, Shopify or Stripe exports. We split gross sales into net cash and commission expense.", cols: ["Dr Bank Clearing", "Dr Commissions Expense", "Cr Gross Sales Revenue"], out: "Balanced QuickBooks journal entry CSV" },
];

export default function Landing() {
  const { user } = useAuth();
  const trustboxRef = useRef(null);
  const ctaTo = user ? "/dashboard" : "/register";

  useEffect(() => {
    document.title = PAGE_TITLE;
    if (window.Trustpilot && trustboxRef.current) {
      window.Trustpilot.loadFromElement(trustboxRef.current, true);
    }
  }, []);
  return (
    <div className="min-h-screen bg-background" data-testid="landing-page">
      <header className="sticky top-0 z-40 border-b border-slate-800/70 bg-[#0b132b]/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto h-16 px-5 sm:px-8 lg:px-16 flex items-center justify-between">
          <Brand />
          <nav className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#modules" className="hover:text-slate-100" data-testid="nav-modules-link">Modules</a>
            <a href="#use-cases" className="hover:text-slate-100" data-testid="nav-use-cases-link">Use cases</a>
            <a href="#trust" className="hover:text-slate-100" data-testid="nav-trust-link">Why firms trust us</a>
            <a href="#pricing" className="hover:text-slate-100" data-testid="nav-pricing-link">Pricing</a>
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            {!user && <Link to="/login" className="text-sm text-slate-300 hover:text-white px-3 py-2" data-testid="landing-signin-link">Sign in</Link>}
            <Link to={ctaTo} className="rounded-lg bg-emerald-500 hover:bg-emerald-400 text-emerald-950 text-sm font-semibold px-4 py-2 transition-colors" data-testid="landing-header-cta">
              {user ? "Open dashboard" : "Start free"}
            </Link>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden grid-bg noise border-b border-slate-800/70">
        <div className="relative max-w-7xl mx-auto px-5 sm:px-8 lg:px-16 pt-16 sm:pt-24 pb-20 grid grid-cols-1 gap-14 lg:grid-cols-[1.05fr_1fr] items-center [&>*]:min-w-0">
          <div>
            <div className="reveal eyebrow mb-5">For bookkeeping & CPA firms</div>
            <h1 className="reveal text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05] text-slate-50" style={{ animationDelay: "60ms" }}>
              The <span className="text-emerald-400">Financial Ingestion Hub</span> for Modern Bookkeepers.
            </h1>
            <p className="reveal mt-6 text-base sm:text-lg text-slate-300 max-w-xl" style={{ animationDelay: "120ms" }} data-testid="hero-subheadline">
              Convert PDF bank statements to Excel, clean up multi-year historical accounting backlogs, and instantly split complex marketplace payouts (Toast, DoorDash, Shopify, LawPay) into balanced QuickBooks-ready journal entries.
            </p>
            <div className="reveal mt-9 flex flex-wrap gap-3" style={{ animationDelay: "180ms" }}>
              <Link to={ctaTo} className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold px-5 py-3 transition-colors" data-testid="hero-primary-cta">
                Start with 5 free pages <ArrowRight className="h-4 w-4" />
              </Link>
              <a href="#modules" className="inline-flex items-center rounded-lg border border-slate-700 hover:border-slate-500 text-slate-200 px-5 py-3 transition-colors" data-testid="hero-secondary-cta">See how it works</a>
            </div>
            <p className="reveal mt-5 text-xs text-slate-500" style={{ animationDelay: "240ms" }}>No credit card required · Files deleted after 1 hour</p>
          </div>
          <HeroPreview />
        </div>
      </section>

      <section className="px-5 sm:px-8 lg:px-16 py-14 max-w-7xl mx-auto" data-testid="landing-trust-badges-section">
        <p className="text-xs uppercase tracking-[0.18em] text-slate-500 mb-6">Works with your clients' platforms</p>
        <TrustBadgesRow />
      </section>

      <Section id="modules" eyebrow="Two modules, one dashboard" title="Everything a cleanup engagement needs" testId="landing-modules-section">
        <div className="grid gap-6 lg:grid-cols-2">
          {MODULES.map((m) => (
            <div key={m.title} className="surface p-6 sm:p-8">
              <m.icon className="h-6 w-6 text-emerald-400" />
              <h3 className="mt-5 text-xl font-semibold text-slate-50">{m.title}</h3>
              <p className="mt-2 text-slate-400">{m.text}</p>
              <div className="mt-6 flex flex-wrap gap-2">
                {m.cols.map((c) => <span key={c} className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs text-slate-300 font-mono">{c}</span>)}
              </div>
              <div className="mt-6 pt-5 border-t border-slate-800 text-sm text-emerald-300">Deliverable: {m.out}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section id="use-cases" eyebrow="Financial utilities for bookkeepers" title="Use Cases" sub="From PDF bank statement conversion to QuickBooks Online payout splitting, one hub handles every ingestion job." testId="landing-use-cases-section">
        <UseCases />
      </Section>

      <Section id="trust" eyebrow="Peer proof" title="Real firms. Real backlogs. Exact pennies." sub="Bookkeepers trust the math because every journal entry is validated to balance before export." testId="landing-trust-section">
        <CaseStudyReviews />
        <div className="mt-10"><SecurityStrip /></div>
      </Section>

      <Section id="pricing" eyebrow="Pricing" title="Start free. Upgrade when the backlog is real." sub="Your first 5 statement pages are on us." testId="landing-pricing-section">
        <PricingMatrix publicMode />
      </Section>

      <footer className="border-t border-slate-800/70">
        {/* Built for Skeptical Bookkeepers Reassurance Strip */}
        <section className="px-5 sm:px-8 lg:px-16 py-10 max-w-6xl mx-auto">
          <div className="rounded-2xl bg-slate-900/80 border border-slate-800 p-6 sm:p-8">
            <div className="text-center max-w-2xl mx-auto mb-6">
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                Built for Skeptical Bookkeepers &amp; CPAs
              </span>
              <h3 className="mt-1.5 text-xl sm:text-2xl font-bold text-white">
                No Hallucinated Pennies. No Client Bank Logins. No Wasted Audit Time.
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left">
              <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/80">
                <div className="text-sm font-semibold text-white mb-1">1. Zero Client Bank Credentials</div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Never link live client bank feeds or store passwords. Upload standard PDFs or redacted statements inside an isolated firm workspace.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/80">
                <div className="text-sm font-semibold text-white mb-1">2. Deterministic $0.00 Math Check</div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Unlike generic AI that guesses numbers, our engine verifies total debits equal total credits to the exact cent before export.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/80">
                <div className="text-sm font-semibold text-white mb-1">3. Audit-Ready QBO &amp; Xero Exports</div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Stop spending hours fixing shifted OCR columns or manually splitting Stripe, Shopify, Toast, LawPay, and Deliveroo payout fees in Excel.
                </p>
              </div>
            </div>
          </div>
        </section>

      
        {/* Supported Global Banks & Payout Platforms Scrolling Marquee */}
<section className="py-16 border-t border-slate-800/80 overflow-hidden">
  <style>{`
    @keyframes bankScrollLeft {
      0% { transform: translateX(0%); }
      100% { transform: translateX(-50%); }
    }
    .animate-bank-row-1 {
      display: flex;
      width: max-content;
      animation: bankScrollLeft 34s linear infinite;
    }
    .animate-bank-row-2 {
      display: flex;
      width: max-content;
      animation: bankScrollLeft 28s linear infinite;
    }
    .animate-bank-row-1:hover,
    .animate-bank-row-2:hover {
      animation-play-state: paused;
    }
  `}</style>

  <div className="text-center max-w-3xl mx-auto px-4 mb-10">
    <span className="inline-block px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 text-xs font-semibold uppercase tracking-wider mb-3">
      Global Coverage · Zero Bank Logins Required
    </span>
    <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
      Works With Major Banks &amp; Payout Platforms Worldwide
    </h2>
    <p className="mt-2.5 text-sm text-slate-400">
      Multi-page PDF extraction &amp; automated fee splitting across the US, UK, Canada, Australia, and the EU.
    </p>
  </div>

  {/* Row 1: Global Banks Scrolling Right-to-Left */}
  <div className="relative w-full overflow-hidden mb-4">
    <div className="animate-bank-row-1">
      {[0, 1].map((loopIdx) => (
        <div key={loopIdx} className="flex items-center gap-3.5 pr-3.5">
          {[
            { name: "Chase", region: "US", badge: "CH", color: "bg-blue-600" },
            { name: "Bank of America", region: "US", badge: "BA", color: "bg-red-600" },
            { name: "Wells Fargo", region: "US", badge: "WF", color: "bg-amber-600" },
            { name: "American Express", region: "US/Global", badge: "AX", color: "bg-sky-600" },
            { name: "Mercury", region: "US", badge: "MC", color: "bg-indigo-600" },
            { name: "Barclays", region: "UK", badge: "BC", color: "bg-cyan-600" },
            { name: "HSBC", region: "UK/Global", badge: "HS", color: "bg-red-600" },
            { name: "Lloyds Bank", region: "UK", badge: "LB", color: "bg-emerald-600" },
            { name: "NatWest", region: "UK", badge: "NW", color: "bg-purple-600" },
            { name: "Monzo Business", region: "UK", badge: "MZ", color: "bg-rose-500" },
            { name: "Tide", region: "UK", badge: "TD", color: "bg-blue-500" },
            { name: "BNP Paribas", region: "EU", badge: "BP", color: "bg-emerald-600" },
            { name: "ING Bank", region: "EU", badge: "IN", color: "bg-orange-500" },
            { name: "Deutsche Bank", region: "EU", badge: "DB", color: "bg-blue-700" },
            { name: "Wise Business", region: "EU/UK", badge: "WS", color: "bg-lime-600" },
            { name: "Revolut Business", region: "EU/UK", badge: "RV", color: "bg-slate-600" },
            { name: "Qonto", region: "EU", badge: "QT", color: "bg-violet-600" },
            { name: "RBC Royal Bank", region: "CA", badge: "RB", color: "bg-blue-600" },
            { name: "TD Bank", region: "CA/US", badge: "TD", color: "bg-green-600" },
            { name: "Scotiabank", region: "CA", badge: "SB", color: "bg-red-600" },
            { name: "CommBank", region: "AU", badge: "CB", color: "bg-yellow-500 text-slate-950" },
            { name: "Westpac", region: "AU", badge: "WP", color: "bg-red-600" },
            { name: "ANZ Bank", region: "AU/NZ", badge: "AZ", color: "bg-sky-600" },
          ].map((bank) => (
            <div
              key={`${loopIdx}-${bank.name}`}
              className="inline-flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-slate-600 transition-colors"
            >
              <span className={`inline-flex items-center justify-center w-6 h-6 rounded-md text-[10px] font-bold text-white shadow-sm ${bank.color}`}>
                {bank.badge}
              </span>
              <span className="text-xs font-semibold text-slate-200 whitespace-nowrap">{bank.name}</span>
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                {bank.region}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  </div>

  {/* Row 2: Merchant & Delivery Payout Platforms Scrolling Right-to-Left */}
  <div className="relative w-full overflow-hidden">
    <div className="animate-bank-row-2">
      {[0, 1].map((loopIdx) => (
        <div key={loopIdx} className="flex items-center gap-3.5 pr-3.5">
          {[
            { name: "Stripe Payouts", badge: "S", color: "bg-indigo-600" },
            { name: "Shopify Payments", badge: "SH", color: "bg-emerald-600" },
            { name: "Square POS", badge: "SQ", color: "bg-slate-700" },
            { name: "PayPal", badge: "PP", color: "bg-blue-600" },
            { name: "Amazon Seller", badge: "AZ", color: "bg-amber-500 text-slate-950" },
            { name: "Etsy", badge: "ET", color: "bg-orange-600" },
            { name: "Toast POS", badge: "TS", color: "bg-orange-500" },
            { name: "Clover", badge: "CL", color: "bg-green-600" },
            { name: "DoorDash", badge: "DD", color: "bg-red-600" },
            { name: "UberEats", badge: "UE", color: "bg-emerald-500 text-slate-950" },
            { name: "Deliveroo", badge: "DL", color: "bg-teal-500 text-slate-950" },
            { name: "Just Eat", badge: "JE", color: "bg-orange-500" },
            { name: "Airbnb Host", badge: "AB", color: "bg-rose-500" },
          ].map((platform) => (
            <div
              key={`${loopIdx}-${platform.name}`}
              className="inline-flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-slate-900/90 border border-emerald-900/50 hover:border-emerald-500/50 transition-colors"
            >
              <span className={`inline-flex items-center justify-center w-6 h-6 rounded-md text-[10px] font-bold text-white shadow-sm ${platform.color}`}>
                {platform.badge}
              </span>
              <span className="text-xs font-semibold text-emerald-100 whitespace-nowrap">{platform.name}</span>
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400">
                Fee Split
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  </div>
</section>


        {/* Verified Software Directory Scrolling Marquee */}
<div className="mt-8 pt-6 border-t border-slate-800/80 overflow-hidden">
  <style>{`
    @keyframes ledgerMarquee {
      0% { transform: translateX(0%); }
      100% { transform: translateX(-50%); }
    }
    .animate-ledger-marquee {
      display: flex;
      width: max-content;
      animation: ledgerMarquee 22s linear infinite;
    }
    .animate-ledger-marquee:hover {
      animation-play-state: paused;
    }
  `}</style>

  <div className="text-center mb-3">
    <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
      Verified &amp; Listed Across Top Software Directories
    </span>
  </div>

  <div className="relative w-full overflow-hidden">
    <div className="animate-ledger-marquee gap-4">
      {[0, 1].map((loopIndex) => (
        <div key={loopIndex} className="flex items-center gap-4 pr-4">
          {/* G2 Badge with Icon */}
          <a
            href="href="https://www.g2.com/contributor/ledgerstream-ai-review-collection-eaa75080-2389-494b-ab24-a3db5c3ef4ff"
"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2.5 px-4 py-2 rounded-lg bg-slate-900/90 border border-slate-700/80 hover:border-orange-500/60 text-slate-200 text-xs font-medium transition-all"
          >
            <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-orange-500 text-white font-extrabold text-[10px] tracking-tighter">
              G2
            </span>
            <span>Listed on <strong>G2</strong></span>
          </a>

          {/* Capterra Badge with Icon */}
          <a
            href="https://www.capterra.com/p/10286660/LedgerStream-AI/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2.5 px-4 py-2 rounded-lg bg-slate-900/90 border border-slate-700/80 hover:border-sky-500/60 text-slate-200 text-xs font-medium transition-all"
          >
            <svg className="w-4 h-4 text-sky-400" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2 3l20 7.5L13.5 14 10 22 2 3z" />
            </svg>
            <span>Verified on <strong>Capterra</strong></span>
          </a>

      {/* Software Advice Badge */}
          <a
            href="https://www.softwareadvice.com/product/793983-LedgerStream-AI/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2.5 px-4 py-2 rounded-lg bg-slate-900/90 border border-slate-700/80 hover:border-amber-500/60 text-slate-200 text-xs font-medium transition-all"
          >
            <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-amber-500 text-slate-950 font-extrabold text-[10px] tracking-tighter">
              SA
            </span>
            <span>Listed on <strong>Software Advice</strong></span>
          </a>
          {/* Trustpilot Badge with Star Icon */}
          <a
            href="https://trustpilot.com"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2.5 px-4 py-2 rounded-lg bg-slate-900/90 border border-slate-700/80 hover:border-emerald-500/60 text-slate-200 text-xs font-medium transition-all"
          >
            <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-emerald-500 text-white">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
            </span>
            <span>Review us on <strong>Trustpilot</strong></span>
          </a>

          {/* GetApp Badge with Icon */}
          <a
            href="https://www.getapp.com/all-software/a/ledgerstream-ai/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2.5 px-4 py-2 rounded-lg bg-slate-900/90 border border-slate-700/80 hover:border-indigo-500/60 text-slate-200 text-xs font-medium transition-all"
          >
            <svg className="w-4 h-4 text-indigo-400" viewBox="0 0 24 24" fill="currentColor">
              <path d="M4 4h7v7H4V4zm9 0h7v7h-7V4zM4 13h7v7H4v-7zm9 3.5L16.5 13 20 16.5 16.5 20 13 16.5z" />
            </svg>
            <span>Featured on <strong>GetApp</strong></span>
          </a>
        </div>
      ))}
    </div>
  </div>
</div>

        <div className="max-w-7xl mx-auto px-5 sm:px-8 lg:px-16 py-10 flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between text-sm text-slate-500">
          <Brand />
          <Link to="/contact" className="hover:text-emerald-300" data-testid="landing-footer-contact-link">Contact Support & Sales</Link>
          <span>© {new Date().getFullYear()} LedgerStream AI. Built for bookkeeping firms.</span>
        </div>

      </footer>
    </div>
  );
}
