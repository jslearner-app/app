import { Loader2 } from "lucide-react";

export const FullScreenLoader = ({ label }) => (
  <div className="min-h-screen flex items-center justify-center bg-background" data-testid="full-screen-loader">
    <div className="flex items-center gap-3 text-slate-400 text-sm">
      <Loader2 className="h-5 w-5 animate-spin text-emerald-400" />
      {label}
    </div>
  </div>
);
