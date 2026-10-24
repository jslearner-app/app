import { Link } from "react-router-dom";

const resetDate = (iso) => (iso ? new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }) : "");

export const UsageMeter = ({ user, compact = false }) => {
  const limit = user.page_limit;
  const used = user.usage_pages;
  const monthly = user.limit_period === "month";
  const pct = Math.min(100, Math.round((used / limit) * 100));
  const exhausted = used >= limit;
  const canUpgrade = user.plan !== "agency";
  const linkText = exhausted
    ? monthly ? (canUpgrade ? "Monthly limit reached. Upgrade" : `Monthly limit reached. Resets ${resetDate(user.period_resets_at)}`) : "Trial used. Upgrade to continue"
    : "View plans";

  return (
    <div className={compact ? "rounded-lg border border-slate-800 bg-slate-900/60 p-3" : "surface p-5"} data-testid={compact ? "sidebar-usage-meter" : "usage-meter"}>
      <div className="flex items-center justify-between text-xs">
        <span className="uppercase tracking-wider text-slate-400">{monthly ? "Pages this month" : "Free trial pages"}</span>
        <span className={`num font-semibold ${exhausted ? "text-amber-300" : "text-slate-100"}`} data-testid={compact ? "sidebar-usage-count" : "usage-pages-used"}>
          {used.toLocaleString()}/{limit.toLocaleString()}
        </span>
      </div>
      <div className="mt-2 h-1.5 rounded-full bg-slate-800 overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${exhausted ? "bg-amber-400" : "bg-emerald-500"}`} style={{ width: `${pct}%` }} />
      </div>
      {monthly && !compact && (
        <div className="mt-2 text-xs text-slate-500" data-testid="usage-reset-date">Resets {resetDate(user.period_resets_at)} (UTC)</div>
      )}
      {(exhausted || !compact) && (monthly ? canUpgrade || exhausted : true) && (
        canUpgrade ? (
          <Link to="/pricing" className="mt-2 inline-block text-xs font-medium text-emerald-400 hover:text-emerald-300" data-testid={compact ? "sidebar-upgrade-link" : "usage-upgrade-link"}>
            {linkText}
          </Link>
        ) : (
          <div className="mt-2 text-xs text-amber-300" data-testid={compact ? "sidebar-limit-note" : "usage-limit-note"}>{linkText}</div>
        )
      )}
    </div>
  );
};
