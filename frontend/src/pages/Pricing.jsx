import { useSearchParams } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { PricingMatrix } from "@/components/billing/PricingMatrix";

export default function Pricing() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const limitHit = params.get("reason") === "trial_limit";

  return (
    <div data-testid="pricing-page">
      {limitHit && (
        <div className="mb-8 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4" data-testid="trial-limit-banner">
          <AlertTriangle className="h-5 w-5 text-amber-300 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-amber-200">You've reached the 5-page free trial limit</div>
            <div className="text-sm text-amber-100/70">You have used {user.pages_used} of 5 free pages. Choose a plan to keep converting statements.</div>
          </div>
        </div>
      )}
      <PageHeader eyebrow="Pricing" title="Choose the plan that fits your firm" description="Cancel anytime from the Stripe Customer Portal." />
      <PricingMatrix currentPlan={user.plan} />
    </div>
  );
}
