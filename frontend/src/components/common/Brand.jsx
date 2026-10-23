import { Link } from "react-router-dom";

export const BrandMark = ({ className = "h-8 w-8" }) => (
  <span className={`${className} inline-flex items-center justify-center rounded-lg bg-emerald-500 text-emerald-950 shrink-0`}>
    <svg viewBox="0 0 24 24" className="h-[60%] w-[60%]" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
      <path d="M4 7h16M4 12h10M4 17h13" />
    </svg>
  </span>
);

export const Brand = ({ to = "/", testId = "brand-link" }) => (
  <Link to={to} data-testid={testId} className="inline-flex items-center gap-2.5 group">
    <BrandMark />
    <span className="font-display font-bold text-[17px] tracking-tight text-slate-50">
      LedgerStream <span className="text-emerald-400">AI</span>
    </span>
  </Link>
);
