import { useSearchParams } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { PricingMatrix } from "@/components/billing/PricingMatrix";
import { resetDate } from "@/components/billing/UsageMeter";

export default function Pricing() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const reason = params.get("reason");
  const limitHit = reason === "trial_limit" || reason === "monthly_limit";
  const monthly = reason === "monthly_limit";

  return (
    <div data-testid="pricing-page">
      {limitHit && (
        <div className="mb-8 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4" data-testid="trial-limit-banner">
          <AlertTriangle className="h-5 w-5 text-amber-300 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-amber-200">{monthly ? `You've reached your ${user.page_limit.toLocaleString()}-page monthly limit` : "You've reached the 5-page free trial limit"}</div>
            <div className="text-sm text-amber-100/70">
              {monthly
                ? `You have used ${user.usage_pages.toLocaleString()} of ${user.page_limit.toLocaleString()} pages this month. ${user.plan === "starter" ? "Upgrade to Agency for 1,000 pages per month, or wait until" : "Your allowance resets on"} ${resetDate(user.period_resets_at)} (UTC).`
                : `You have used ${user.usage_pages} of 5 free pages. Choose a plan to keep converting statements.`}
            </div>
          </div>
        </div>
      )}
      <PageHeader eyebrow="Pricing" title="Choose the plan that fits your firm" description="Cancel anytime from the Stripe Customer Portal." />
      <PricingMatrix currentPlan={user.plan} />
    </div>
  );
}
