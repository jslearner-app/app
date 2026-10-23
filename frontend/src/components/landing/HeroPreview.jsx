import { CheckCircle2, FileText } from "lucide-react";

const ROWS = [
  ["09/02", "TOAST INC DAILY SETTLEMENT", "", "2,184.53"],
  ["09/03", "SYSCO FOOD SERVICES", "1,206.40", ""],
  ["09/04", "CHECK #1187", "640.00", ""],
  ["09/05", "ACH DEPOSIT DOORDASH PAYOUT", "", "1,431.18"],
];

export const HeroPreview = () => (
  <div className="reveal relative" style={{ animationDelay: "200ms" }} data-testid="hero-product-preview">
    <div className="rounded-2xl border border-slate-700/80 bg-[#0f1830]/95 shadow-2xl shadow-black/40 overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
        <FileText className="h-4 w-4 text-emerald-400" />
        <span className="text-xs text-slate-300 font-medium">burger-shack-sept.pdf</span>
        <span className="ml-auto text-[10px] uppercase tracking-wider text-slate-500">3 pages · 41 txns</span>
      </div>
      <table className="w-full text-[12px] font-mono">
        <thead>
          <tr className="text-slate-500 text-[10px] uppercase tracking-wider">
            <th className="text-left px-4 py-2 font-medium">Date</th>
            <th className="text-left px-2 py-2 font-medium">Description</th>
            <th className="text-right px-2 py-2 font-medium">Withdr.</th>
            <th className="text-right px-4 py-2 font-medium">Deposit</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r[1]} className="border-t border-slate-800/70 text-slate-300">
              <td className="px-4 py-2 text-slate-500">{r[0]}</td>
              <td className="px-2 py-2 truncate max-w-[150px] sm:max-w-none">{r[1]}</td>
              <td className="px-2 py-2 text-right text-rose-300">{r[2]}</td>
              <td className="px-4 py-2 text-right text-emerald-300">{r[3]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    <div className="relative -mt-6 ml-6 sm:ml-16 mr-2 rounded-xl border border-emerald-500/30 bg-[#0b132b] p-4 shadow-xl shadow-black/40">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-slate-200">DoorDash payout · 30%</span>
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-950 border border-emerald-500/40 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
          <CheckCircle2 className="h-3 w-3" />Balanced: Ready to Export
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] font-mono">
        <div><div className="text-slate-500">Dr Bank</div><div className="text-slate-100">$191.85</div></div>
        <div><div className="text-slate-500">Dr Comm.</div><div className="text-slate-100">$81.80</div></div>
        <div><div className="text-slate-500">Cr Sales</div><div className="text-slate-100">$273.65</div></div>
      </div>
    </div>
  </div>
);
