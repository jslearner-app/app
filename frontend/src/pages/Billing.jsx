import { useEffect, useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader } from "@/components/common/PageHeader";
import { UsageMeter } from "@/components/billing/UsageMeter";
import { PricingMatrix } from "@/components/billing/PricingMatrix";

const PLAN_LABEL = { free: "Free trial", starter: "Starter · $99/month", agency: "Agency · $199/month" };

export default function Billing() {
  const { user, refreshUser } = useAuth();
  const [billing, setBilling] = useState(null);
  const [opening, setOpening] = useState(false);

  useEffect(() => {
    refreshUser();
    api.get("/billing/summary").then(({ data }) => setBilling(data)).catch((e) => toast.error(errMsg(e)));
  }, [refreshUser]);

  const openPortal = async () => {
    setOpening(true);
    try {
      const { data } = await api.post("/billing/portal", { origin_url: window.location.origin });
      window.location.href = data.url;
    } catch (e) {
      toast.error(errMsg(e));
      setOpening(false);
    }
  };

  return (
    <div data-testid="billing-page">
      <PageHeader eyebrow="Subscription" title="Billing" description="Manage your plan, usage and payment details." />
      <div className="grid gap-4 md:grid-cols-[1.2fr_1fr] mb-10">
        <div className="surface p-6 flex flex-col">
          <div className="text-[11px] uppercase tracking-wider text-slate-500">Current plan</div>
          <div className="mt-2 font-display text-2xl font-semibold text-slate-50" data-testid="billing-current-plan">{PLAN_LABEL[user.plan] || user.plan}</div>
          <p className="mt-2 text-sm text-slate-400">
            {user.plan === "free" ? "Your free trial includes 5 bank statement pages. Upgrade for unlimited conversions." : "Unlimited statement conversions are active on your account."}
          </p>
          <div className="flex-1" />
          <div className="mt-6 rounded-lg border border-slate-800 bg-slate-950/40 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3" data-testid="customer-portal-card">
            <div>
              <div className="text-sm font-medium text-slate-100">Stripe Customer Portal</div>
              <div className="text-xs text-slate-400">Update cards, download invoices or cancel anytime.</div>
            </div>
            <Button onClick={openPortal} disabled={!billing?.has_portal || opening} variant="outline" className="border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800" data-testid="open-customer-portal-button">
              {opening ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <ExternalLink className="h-4 w-4 mr-1.5" />}Manage subscription
            </Button>
          </div>
        </div>
        <UsageMeter user={user} />
      </div>
      <h2 className="text-base md:text-lg font-semibold text-slate-50 mb-4">Plans</h2>
      <PricingMatrix currentPlan={user.plan} />
    </div>
  );
}
