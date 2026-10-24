import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { resetDate } from "@/components/billing/UsageMeter";

const THRESHOLD = 0.8;
const DISMISS_KEY = "ls-low-page-alert-dismissed";

const UpgradeAction = ({ user }) => {
  const [busy, setBusy] = useState(false);
  const cls = "inline-flex items-center gap-1.5 rounded-md bg-yellow-400 hover:bg-yellow-300 text-slate-900 text-sm font-semibold px-3.5 py-2 transition-colors whitespace-nowrap";

  if (user.plan === "agency") {
    return <a href="mailto:sales@ledgerstreamai.com" className={cls} data-testid="low-page-alert-action">Contact sales <ArrowRight className="h-4 w-4" /></a>;
  }
  if (user.plan === "free") {
    return <Link to="/pricing" className={cls} data-testid="low-page-alert-action">Upgrade now <ArrowRight className="h-4 w-4" /></Link>;
  }
  const openPortal = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/billing/portal", { origin_url: window.location.origin });
      window.location.href = data.url;
    } catch (e) {
      toast.error(errMsg(e));
      setBusy(false);
    }
  };
  return (
    <button onClick={openPortal} disabled={busy} className={cls} data-testid="low-page-alert-action">
      {busy && <Loader2 className="h-4 w-4 animate-spin" />}Upgrade to Agency <ArrowRight className="h-4 w-4" />
    </button>
  );
};

export const LowPageAlert = ({ user }) => {
  const level = `${user.plan}:${user.usage_pages >= user.page_limit ? "full" : "low"}`;
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem(DISMISS_KEY) === level);
  if (!user.page_limit || user.usage_pages < user.page_limit * THRESHOLD || dismissed) return null;

  const full = user.usage_pages >= user.page_limit;
  const monthly = user.limit_period === "month";
  const scope = monthly ? "this month's" : "your free trial";
  const title = full ? `You've used all of ${scope} pages` : `You've used ${Math.round((user.usage_pages / user.page_limit) * 100)}% of ${scope} pages`;
  const detail = `${user.usage_pages.toLocaleString()} of ${user.page_limit.toLocaleString()} pages used${monthly ? `, resets ${resetDate(user.period_resets_at)} (UTC)` : ""}. ${
    user.plan === "agency" ? "Need more than 1,000 pages a month? Our sales team can set up a custom plan." : "Upgrade now so statement conversions don't stop mid-engagement."
  }`;

  const dismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, level);
    setDismissed(true);
  };

  return (
    <div role="alert" className="mb-8 flex flex-col gap-3 rounded-xl border border-yellow-400/50 bg-[#1e293b] px-4 py-3.5 sm:flex-row sm:items-center reveal" data-testid="low-page-alert">
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <span className="mt-0.5 h-8 w-8 shrink-0 rounded-lg bg-yellow-400/15 border border-yellow-400/40 flex items-center justify-center">
          <AlertTriangle className="h-4 w-4 text-yellow-300" />
        </span>
        <div className="min-w-0">
          <div className="font-semibold text-yellow-200" data-testid="low-page-alert-title">{title}</div>
          <div className="text-sm text-slate-300" data-testid="low-page-alert-detail">{detail}</div>
        </div>
      </div>
      <div className="flex items-center gap-2 sm:shrink-0">
        <UpgradeAction user={user} />
        <button onClick={dismiss} className="p-2 rounded-md text-slate-400 hover:text-slate-100 hover:bg-slate-700/60" aria-label="Dismiss alert" data-testid="low-page-alert-dismiss">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};
