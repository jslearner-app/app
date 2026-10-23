import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api, delay, errMsg } from "@/lib/api";
import { money } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";
import { ClientSelect } from "@/components/common/ClientSelect";
import { FileDropzone } from "@/components/common/FileDropzone";
import { IsolationBadge } from "@/components/trust/TrustSignals";
import { ParsingLoader } from "./ParsingLoader";
import { StatementGrid } from "./StatementGrid";
import { ReconciliationBanner } from "./ReconciliationBanner";
import { notifyHistoryChanged } from "@/hooks/useReviewCount";

const Stat = ({ label, value, testId, tone = "text-slate-50" }) => (
  <div className="surface px-4 py-3">
    <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
    <div className={`mt-1 num text-lg font-semibold ${tone}`} data-testid={testId}>{value}</div>
  </div>
);

export const ConverterPanel = ({ clients, onConverted }) => {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [clientId, setClientId] = useState("");
  const [parsing, setParsing] = useState(null);
  const [statement, setStatement] = useState(null);
  const [engine, setEngine] = useState(null);

  useEffect(() => {
    api.get("/statements/engine").then(({ data }) => setEngine(data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!clientId && clients.length) setClientId(clients[0].id);
  }, [clients, clientId]);

  const upload = async (file) => {
    if (!clientId) return toast.error("Select a client profile first");
    if (user.page_limit && user.pages_used >= user.page_limit) return navigate("/pricing?reason=trial_limit");
    if (engine && !engine.configured) return toast.error("Amazon Textract is not connected yet. Add your AWS keys to enable PDF parsing.");
    setParsing(file.name);
    const form = new FormData();
    form.append("file", file);
    form.append("client_id", clientId);
    try {
      const [res] = await Promise.all([api.post("/statements", form), delay(3800)]);
      setStatement(res.data);
      toast.success(`${res.data.summary.transactions} transactions extracted from ${res.data.pages} page(s)`);
      onConverted?.();
      notifyHistoryChanged();
    } catch (e) {
      if (e.response?.status === 402) {
        toast.error(errMsg(e));
        navigate("/pricing?reason=trial_limit");
      } else toast.error(errMsg(e));
    } finally {
      setParsing(null);
      refreshUser();
    }
  };

  if (parsing) return <ParsingLoader filename={parsing} />;

  if (statement) {
    const s = statement.summary;
    return (
      <div className="space-y-5" data-testid="statement-results">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <FileText className="h-5 w-5 text-emerald-400 shrink-0" />
            <div className="min-w-0">
              <div className="truncate font-semibold text-slate-100" data-testid="statement-filename">{statement.filename}</div>
              <div className="text-xs text-slate-400">{statement.client_name} · {statement.pages} page(s) · Amazon Textract</div>
            </div>
          </div>
          <Button variant="outline" onClick={() => setStatement(null)} data-testid="convert-another-button" className="border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800">
            <RotateCcw className="h-4 w-4 mr-1.5" />Convert another
          </Button>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Stat label="Transactions" value={s.transactions} testId="summary-transactions" />
          <Stat label="Total deposits" value={money(s.total_deposits)} tone="text-emerald-300" testId="summary-deposits" />
          <Stat label="Total withdrawals" value={money(s.total_withdrawals)} tone="text-rose-300" testId="summary-withdrawals" />
          <Stat label="Closing balance" value={money(s.closing_balance)} testId="summary-closing-balance" />
        </div>
        <ReconciliationBanner rec={s.reconciliation} />
        <StatementGrid key={statement.id} statement={statement} onSaved={setStatement} />
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]" data-testid="converter-panel">
      <div>
        {engine && !engine.configured && (
          <div className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-200" data-testid="textract-not-configured-banner">
            Amazon Textract is not connected yet. Add <span className="num">AWS_ACCESS_KEY_ID</span>, <span className="num">AWS_SECRET_ACCESS_KEY</span> and <span className="num">AWS_REGION</span> to start parsing statements.
          </div>
        )}
        <FileDropzone
          accept=".pdf"
          title="Drop a bank statement PDF here"
          hint="Multi-page PDFs supported · or click to browse"
          onFile={upload}
          disabled={!clients.length}
          testId="pdf-upload-dropzone"
        />
        <IsolationBadge testId="converter-isolation-badge" />
      </div>
      <div className="space-y-4">
        <div>
          <label className="text-xs uppercase tracking-wider text-slate-400">Client profile</label>
          <div className="mt-2"><ClientSelect clients={clients} value={clientId} onChange={setClientId} testId="converter-client-select" /></div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-400 space-y-2">
          <div className="text-slate-200 font-medium">Output columns</div>
          <p>Date · Description · Reference/Check # · Withdrawals · Deposits · Balance</p>
          {user.page_limit && (
            <p className="text-xs" data-testid="converter-pages-remaining">
              <span className="num text-emerald-300">{Math.max(user.page_limit - user.pages_used, 0)}</span> of {user.page_limit} free trial pages remaining
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
