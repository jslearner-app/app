import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { money } from "@/lib/format";

export const VarianceNote = ({ variance, fileFees }) => {
  if (!variance) return null;
  if (!variance.flagged) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-4 py-2.5 text-xs text-emerald-300" data-testid="payout-variance-match">
        <CheckCircle2 className="h-4 w-4 shrink-0" />
        Net deposit matches the file's net total of <span className="num font-semibold">{money(variance.file_net)}</span>.
      </div>
    );
  }
  const hint = fileFees
    ? "Check the file for refunds, chargebacks or deposits split across accounts."
    : "Adjust the commission rate, or check the file for refunds, tips, taxes or adjustments not covered by the rate.";
  return (
    <div className="flex gap-3 rounded-lg border border-amber-500/40 bg-amber-950/40 px-4 py-3 text-sm" data-testid="payout-variance-note">
      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-amber-300" />
      <div className="space-y-1 min-w-0">
        <div className="font-semibold text-amber-200">Payout variance flagged</div>
        <p className="text-amber-100/80 text-xs leading-relaxed">
          The file reports a net payout of <span className="num font-semibold text-amber-100" data-testid="variance-file-net">{money(variance.file_net)}</span>, but the journal entry deposits{" "}
          <span className="num font-semibold text-amber-100" data-testid="variance-calculated-net">{money(variance.calculated_net)}</span>, a difference of{" "}
          <span className="num font-semibold text-amber-100" data-testid="variance-difference">{money(variance.difference)}</span>. {hint}
        </p>
      </div>
    </div>
  );
};
