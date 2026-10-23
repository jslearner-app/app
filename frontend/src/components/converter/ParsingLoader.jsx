import { useEffect, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";

const STEPS = [
  "Parsing statement structure via AWS Textract...",
  "Extracting tabular transaction coordinates...",
  "Normalizing columns with Pandas...",
  "Validating running balances...",
];

export const ParsingLoader = ({ filename }) => {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 900);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="surface p-6 sm:p-10" data-testid="statement-parsing-loader">
      <div className="relative mx-auto h-36 w-28 rounded-lg border border-slate-700 bg-slate-950/60 overflow-hidden">
        {[...Array(7)].map((_, i) => (
          <div key={i} className="mx-3 mt-3 h-1.5 rounded bg-slate-800" style={{ width: `${60 + ((i * 17) % 35)}%` }} />
        ))}
        <div className="scan-bar absolute inset-x-0 top-0 h-8 bg-emerald-400/20 border-b border-emerald-400/70" />
      </div>
      <p className="mt-6 text-center font-display font-semibold text-slate-100" data-testid="parsing-status-text">{STEPS[0]}</p>
      <p className="mt-1 text-center text-xs text-slate-500 truncate">{filename}</p>
      <ul className="mt-6 mx-auto max-w-sm space-y-2">
        {STEPS.map((s, i) => (
          <li key={s} className={`flex items-center gap-2 text-sm transition-colors ${i <= step ? "text-slate-200" : "text-slate-600"}`}>
            {i < step ? <CheckCircle2 className="h-4 w-4 text-emerald-400" /> : i === step ? <Loader2 className="h-4 w-4 animate-spin text-emerald-400" /> : <span className="h-4 w-4 rounded-full border border-slate-700" />}
            {s}
          </li>
        ))}
      </ul>
    </div>
  );
};
