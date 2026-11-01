import { useState } from "react";
import { CheckCircle2, Loader2, RefreshCw, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";

const STATUS_COPY = {
  ready: { label: "Document AI is working", cls: "text-emerald-300" },
  not_configured: { label: "Google keys missing", cls: "text-amber-300" },
  invalid_credentials: { label: "Service account key rejected", cls: "text-rose-300" },
  permission_denied: { label: "Missing Document AI permission", cls: "text-rose-300" },
  processor_not_found: { label: "Processor not found", cls: "text-rose-300" },
  unreachable: { label: "Document AI unreachable", cls: "text-rose-300" },
  parse_mismatch: { label: "No transactions extracted", cls: "text-amber-300" },
  docai_error: { label: "Document AI error", cls: "text-rose-300" },
};

const Step = ({ s }) => (
  <li className="flex gap-2" data-testid={`engine-check-step-${s.id}`} data-ok={s.ok}>
    {s.ok ? <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-emerald-400" /> : <XCircle className="h-4 w-4 mt-0.5 shrink-0 text-rose-400" />}
    <div className="min-w-0">
      <div className="text-slate-200 text-xs font-medium">{s.label}</div>
      <div className="text-[11px] text-slate-400 break-words">{s.detail}</div>
    </div>
  </li>
);

export const EngineCheck = ({ initial }) => {
  const [check, setCheck] = useState(initial || null);
  const [running, setRunning] = useState(false);
  const copy = check ? STATUS_COPY[check.status] || STATUS_COPY.docai_error : null;

  const run = async () => {
    setRunning(true);
    try {
      const { data } = await api.post("/statements/engine/check");
      setCheck(data);
      if (data.status === "ready") toast.success("Document AI works end to end. Upload a real statement to convert it.");
      else toast.error(`Check complete: ${(STATUS_COPY[data.status] || STATUS_COPY.docai_error).label}`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 space-y-3" data-testid="engine-check-card">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm text-slate-200 font-medium">Document AI connection</div>
        {copy && <span className={`text-[11px] font-semibold ${copy.cls}`} data-testid="engine-check-status" data-status={check.status}>{copy.label}</span>}
      </div>
      {check ? (
        <>
          <ul className="space-y-2" data-testid="engine-check-steps">{check.steps.map((s) => <Step key={s.id} s={s} />)}</ul>
          <div className="text-[11px] text-slate-500" data-testid="engine-check-time">Checked {new Date(check.checked_at).toLocaleString()}</div>
        </>
      ) : (
        <p className="text-xs text-slate-400">Send a built-in sample statement through Google Document AI and the parser to confirm everything works. No pages are charged.</p>
      )}
      <Button onClick={run} disabled={running} variant="outline" className="w-full h-9 border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800 text-xs" data-testid="engine-check-button">
        {running ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5 mr-1.5" />}
        {check ? "Run check again" : "Run connection check"}
      </Button>
    </div>
  );
};
