import { useEffect } from "react";
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
  { icon: FileSpreadsheet, title: "Bank Statement Converter", text: "Drop multi-page PDF statements. Amazon Textract table extraction and a Pandas pipeline return a flat, editable ledger.", cols: ["Date", "Description", "Reference/Check #", "Withdrawals", "Deposits", "Balance"], out: "Excel / CSV ledger for backlogs" },
  { icon: Scale, title: "Merchant Payout Splitter", text: "Upload Toast, DoorDash, UberEats, Shopify or Stripe exports. We split gross sales into net cash and commission expense.", cols: ["Dr Bank Clearing", "Dr Commissions Expense", "Cr Gross Sales Revenue"], out: "Balanced QuickBooks journal entry CSV" },
];

export default function Landing() {
  const { user } = useAuth();
  const ctaTo = user ? "/dashboard" : "/register";
  useEffect(() => {
    document.title = PAGE_TITLE;
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
        <div className="relative max-w-7xl mx-auto px-5 sm:px-8 lg:px-16 pt-16 sm:pt-24 pb-20 grid gap-14 lg:grid-cols-[1.05fr_1fr] items-center">
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
        <div className="max-w-7xl mx-auto px-5 sm:px-8 lg:px-16 py-10 flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between text-sm text-slate-500">
          <Brand />
          <span>© {new Date().getFullYear()} LedgerStream AI. Built for bookkeeping firms.</span>
        </div>
      </footer>
    </div>
  );
}
