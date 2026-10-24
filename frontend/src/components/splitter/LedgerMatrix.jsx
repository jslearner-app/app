import { CheckCircle2, AlertTriangle } from "lucide-react";
import { money } from "@/lib/format";

export const LedgerMatrix = ({ ledger }) => {
  const balanced = ledger.balanced;
  return (
    <div className="surface overflow-hidden" data-testid="ledger-matrix">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-5 py-4 border-b border-slate-800">
        <div>
          <div className="font-display font-semibold text-slate-100">Double-entry journal matrix</div>
          <div className="text-xs text-slate-400">All amounts rounded to exactly two decimals (ROUND_HALF_UP)</div>
        </div>
        {balanced ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-950 border border-emerald-500/40 px-3 py-1 text-xs font-semibold text-emerald-300" data-testid="ledger-balanced-badge">
            <CheckCircle2 className="h-3.5 w-3.5" />Balanced: Ready to Export
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-950 border border-amber-500/40 px-3 py-1 text-xs font-semibold text-amber-300" data-testid="ledger-unbalanced-badge">
            <AlertTriangle className="h-3.5 w-3.5" />Out of balance
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-slate-400 bg-[#16203a]">
              <th className="text-left px-5 py-3 font-semibold">Account</th>
              <th className="text-left px-5 py-3 font-semibold">Memo</th>
              <th className="text-right px-5 py-3 font-semibold">Debit</th>
              <th className="text-right px-5 py-3 font-semibold">Credit</th>
            </tr>
          </thead>
          <tbody>
            {ledger.lines.map((l, i) => (
              <tr key={l.account} className="border-b border-slate-800/70" data-testid={`ledger-line-${i}`}>
                <td className={`px-5 py-3.5 font-medium text-slate-100 ${l.side === "credit" ? "pl-10" : ""}`}>
                  <span className={`mr-2 text-[10px] font-semibold uppercase ${l.side === "debit" ? "text-sky-300" : "text-emerald-300"}`}>{l.side === "debit" ? "Dr" : "Cr"}</span>
                  {l.account}
                </td>
                <td className="px-5 py-3.5 text-slate-400">{l.memo}</td>
                <td className="px-5 py-3.5 text-right num text-slate-100" data-testid={`ledger-line-${i}-debit`}>{l.debit ? money(l.debit) : ""}</td>
                <td className="px-5 py-3.5 text-right num text-slate-100" data-testid={`ledger-line-${i}-credit`}>{l.credit ? money(l.credit) : ""}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-slate-900/80">
              <td className="px-5 py-4 font-semibold text-slate-200" colSpan={2}>Totals</td>
              <td className="px-5 py-4 text-right num font-semibold text-slate-50 border-t-2 border-emerald-500/60" data-testid="ledger-total-debits">{money(ledger.total_debits)}</td>
              <td className="px-5 py-4 text-right num font-semibold text-slate-50 border-t-2 border-emerald-500/60" data-testid="ledger-total-credits">{money(ledger.total_credits)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div className="px-5 py-4 grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 text-xs">
        <span className="text-slate-400 w-14">Debits</span>
        <div className="h-2 rounded-full bg-sky-400/70" />
        <span className="text-slate-400 w-14">Credits</span>
        <div className="h-2 rounded-full bg-emerald-400/80" style={{ width: balanced ? "100%" : "92%" }} />
        <span className="text-slate-400">Debit/credit difference</span>
        <span className="num text-slate-200" data-testid="ledger-difference">{money(ledger.difference)}</span>
      </div>
    </div>
  );
};
