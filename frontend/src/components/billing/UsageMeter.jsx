import { Link } from "react-router-dom";

export const UsageMeter = ({ user, compact = false }) => {
  const limit = user.page_limit;
  if (!limit) {
    return (
      <div className="surface p-5" data-testid="usage-meter">
        <div className="text-xs uppercase tracking-wider text-slate-400">Pages converted</div>
        <div className="mt-2 num text-3xl font-semibold text-slate-50" data-testid="usage-pages-used">{user.pages_used}</div>
        <div className="mt-1 text-xs text-emerald-400">Unlimited on your {user.plan} plan</div>
      </div>
    );
  }
  const pct = Math.min(100, Math.round((user.pages_used / limit) * 100));
  const exhausted = user.pages_used >= limit;
  return (
    <div className={compact ? "rounded-lg border border-slate-800 bg-slate-900/60 p-3" : "surface p-5"} data-testid={compact ? "sidebar-usage-meter" : "usage-meter"}>
      <div className="flex items-center justify-between text-xs">
        <span className="uppercase tracking-wider text-slate-400">Free trial pages</span>
        <span className={`num font-semibold ${exhausted ? "text-amber-300" : "text-slate-100"}`} data-testid={compact ? "sidebar-usage-count" : "usage-pages-used"}>
          {user.pages_used}/{limit}
        </span>
      </div>
      <div className="mt-2 h-1.5 rounded-full bg-slate-800 overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${exhausted ? "bg-amber-400" : "bg-emerald-500"}`} style={{ width: `${pct}%` }} />
      </div>
      {(exhausted || !compact) && (
        <Link to="/pricing" className="mt-2 inline-block text-xs font-medium text-emerald-400 hover:text-emerald-300" data-testid={compact ? "sidebar-upgrade-link" : "usage-upgrade-link"}>
          {exhausted ? "Trial used. Upgrade to continue" : "View plans"}
        </Link>
      )}
    </div>
  );
};
