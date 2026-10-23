import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { TrustBadgesRow, CaseStudyReviews } from "@/components/trust/TrustSignals";

const STEPS = [
  { n: "01", title: "Create a client profile", to: "/clients" },
  { n: "02", title: "Drop a statement or payout file", to: null },
  { n: "03", title: "Export to Excel or QuickBooks", to: null },
];

export const OnboardingTrust = () => (
  <section className="mb-10 rounded-2xl border border-slate-800 bg-[#0d1630] p-5 sm:p-8 space-y-8" data-testid="onboarding-trust-section">
    <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <div className="eyebrow mb-2">Getting started</div>
        <h2 className="text-lg md:text-xl font-semibold text-slate-50">Built for the stacks your clients already run on</h2>
      </div>
      <ol className="grid gap-2 sm:grid-cols-3 lg:w-[620px]">
        {STEPS.map((s) => (
          <li key={s.n} className="rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2.5 text-sm text-slate-300 flex items-center gap-2">
            <span className="num text-xs text-emerald-400">{s.n}</span>
            {s.to ? (
              <Link to={s.to} className="hover:text-emerald-300 inline-flex items-center gap-1" data-testid="onboarding-create-client-link">
                {s.title}<ArrowRight className="h-3 w-3" />
              </Link>
            ) : s.title}
          </li>
        ))}
      </ol>
    </div>
    <TrustBadgesRow compact />
    <CaseStudyReviews compact />
  </section>
);
