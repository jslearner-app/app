import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { money } from "@/lib/format";

export const ReconciliationBanner = ({ rec }) => {
  if (!rec) return null;
  if (rec.status === "unavailable") {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-3 text-sm text-slate-300" data-testid="reconciliation-unavailable">
        <Info className="h-4 w-4 mt-0.5 text-slate-400 shrink-0" />
        {rec.message}
      </div>
    );
  }
  if (rec.status === "reconciled") {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-sm" data-testid="reconciliation-ok">
        <CheckCircle2 className="h-4 w-4 mt-0.5 text-emerald-400 shrink-0" />
        <span className="text-emerald-200">
          Reconciled: opening <span className="num">{money(rec.opening_balance)}</span> plus deposits minus withdrawals equals the closing balance of <span className="num">{money(rec.reported_closing)}</span>.
        </span>
      </div>
    );
  }
  const rows = rec.mismatched_rows || [];
  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm" data-testid="reconciliation-warning">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-4 w-4 mt-0.5 text-amber-300 shrink-0" />
        <div className="min-w-0">
          <div className="font-semibold text-amber-200">Transactions don't add up to the statement's closing balance</div>
          <div className="mt-1 text-amber-100/80">
            Computed closing <span className="num">{money(rec.computed_closing)}</span> vs. statement <span className="num">{money(rec.reported_closing)}</span>
            {" "}(difference <span className="num" data-testid="reconciliation-difference">{money(rec.difference)}</span>).
            {rows.length > 0 && ` ${rows.length} row(s) break the running balance and are highlighted below. Edit them to fix extraction errors.`}
          </div>
          {rows.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-amber-100/70 num" data-testid="reconciliation-mismatch-list">
              {rows.slice(0, 5).map((m) => (
                <li key={m.id}>Row {m.row} ({m.date}): expected {money(m.expected)}, statement shows {money(m.actual)}</li>
              ))}
              {rows.length > 5 && <li>and {rows.length - 5} more</li>}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
