import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";
import { CheckoutTrustBadges } from "@/components/trust/TrustSignals";

const STARTER = ["Up to 200 parsed pages per month", "Merchant Payout Splitter for all 5 platforms", "Excel, CSV & QuickBooks journal exports", "Client profiles & conversion history"];
const AGENCY = ["Everything in Starter", "Up to 1,000 parsed pages per month", "Built for multi-client bookkeeping firms", "Priority parsing queue", "Priority support"];

const Features = ({ items }) => (
  <ul className="mt-6 space-y-3">
    {items.map((f) => (
      <li key={f} className="flex items-start gap-2.5 text-sm text-slate-300">
        <Check className="h-4 w-4 mt-0.5 text-emerald-400 shrink-0" />
        {f}
      </li>
    ))}
  </ul>
);

const Price = ({ amount }) => (
  <div className="mt-4 flex items-baseline gap-1">
    <span className="num text-4xl font-semibold text-slate-50">${amount}</span>
    <span className="text-sm text-slate-400">/month</span>
  </div>
);

export const PricingMatrix = ({ publicMode = false, currentPlan }) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(null);

  const checkout = async (plan) => {
    if (publicMode) return navigate("/register");
    setLoading(plan);
    try {
      const { data } = await api.post("/payments/checkout", { plan, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch (e) {
      toast.error(errMsg(e));
      setLoading(null);
    }
  };

  const cta = (plan, label) => {
    const isCurrent = currentPlan === plan;
    return (
      <Button
        onClick={() => checkout(plan)}
        disabled={isCurrent || loading !== null}
        data-testid={`checkout-${plan}-button`}
        className={`mt-8 w-full h-11 font-semibold ${plan === "starter" ? "bg-emerald-500 hover:bg-emerald-400 text-emerald-950" : "bg-slate-100 hover:bg-white text-slate-900"}`}
      >
        {loading === plan && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
        {isCurrent ? "Current plan" : publicMode ? "Start 5-page free trial" : label}
      </Button>
    );
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1.45fr_1fr]" data-testid="pricing-matrix">
      <div className="surface border-emerald-500/40 p-6 sm:p-8 grid gap-8 sm:grid-cols-[1fr_auto]" data-testid="pricing-tier-starter">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold text-slate-50">Starter</h3>
            <span className="rounded-full bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-300">Most popular</span>
          </div>
          <p className="mt-1 text-sm text-slate-400">For solo bookkeepers and growing practices.</p>
          <Price amount={99} />
          <Features items={STARTER} />
          {cta("starter", "Subscribe to Starter")}
        </div>
        <div className="sm:w-52 sm:border-l sm:border-slate-800 sm:pl-6 flex flex-col justify-center">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-3">Trusted checkout</div>
          <CheckoutTrustBadges />
        </div>
      </div>
      <div className="surface p-6 sm:p-8 flex flex-col" data-testid="pricing-tier-agency">
        <h3 className="text-lg font-semibold text-slate-50">Agency</h3>
        <p className="mt-1 text-sm text-slate-400">For firms managing many client books.</p>
        <Price amount={199} />
        <Features items={AGENCY} />
        <div className="flex-1" />
        {cta("agency", "Subscribe to Agency")}
      </div>
    </div>
  );
};
