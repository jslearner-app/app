import { useState } from "react";
import { CheckCircle2, Loader2, RefreshCw, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, errMsg } from "@/lib/api";

const STATUS_COPY = {
  ready: { label: "Textract is working", cls: "text-emerald-300" },
  not_configured: { label: "AWS keys missing", cls: "text-amber-300" },
  scp_blocked: { label: "Blocked by AWS Organization", cls: "text-rose-300" },
  iam_denied: { label: "AWS user lacks permission", cls: "text-rose-300" },
  invalid_keys: { label: "AWS keys rejected", cls: "text-rose-300" },
  not_subscribed: { label: "Textract not enabled", cls: "text-rose-300" },
  unreachable: { label: "Textract unreachable", cls: "text-rose-300" },
  parse_mismatch: { label: "Parsing check failed", cls: "text-amber-300" },
  textract_error: { label: "Textract error", cls: "text-rose-300" },
};

const Step = ({ s }) => (
  <li className="flex gap-2" data-testid={`textract-check-step-${s.id}`} data-ok={s.ok}>
    {s.ok ? <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-emerald-400" /> : <XCircle className="h-4 w-4 mt-0.5 shrink-0 text-rose-400" />}
    <div className="min-w-0">
      <div className="text-slate-200 text-xs font-medium">{s.label}</div>
      <div className="text-[11px] text-slate-400 break-words">{s.detail}</div>
    </div>
  </li>
);

export const TextractCheck = ({ initial }) => {
  const [check, setCheck] = useState(initial || null);
  const [running, setRunning] = useState(false);
  const copy = check ? STATUS_COPY[check.status] || STATUS_COPY.textract_error : null;

  const run = async () => {
    setRunning(true);
    try {
      const { data } = await api.post("/statements/engine/check");
      setCheck(data);
      if (data.status === "ready") toast.success("Textract works end to end. Upload a real statement to convert it.");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 space-y-3" data-testid="textract-check-card">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm text-slate-200 font-medium">Textract connection</div>
        {copy && <span className={`text-[11px] font-semibold ${copy.cls}`} data-testid="textract-check-status" data-status={check.status}>{copy.label}</span>}
      </div>
      {check ? (
        <>
          <ul className="space-y-2" data-testid="textract-check-steps">{check.steps.map((s) => <Step key={s.id} s={s} />)}</ul>
          <div className="text-[11px] text-slate-500" data-testid="textract-check-time">Checked {new Date(check.checked_at).toLocaleString()}</div>
        </>
      ) : (
        <p className="text-xs text-slate-400">Send a built-in sample statement through Textract and the parser to confirm everything works. No pages are charged.</p>
      )}
      <Button onClick={run} disabled={running} variant="outline" className="w-full h-9 border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800 text-xs" data-testid="textract-check-button">
        {running ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5 mr-1.5" />}
        {check ? "Run check again" : "Run connection check"}
      </Button>
    </div>
  );
};
