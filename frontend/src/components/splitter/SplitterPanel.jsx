import { useEffect, useRef, useState } from "react";
import { Download, Loader2, Calculator, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, downloadFile, errMsg } from "@/lib/api";
import { money, platformMeta } from "@/lib/format";
import { ClientSelect } from "@/components/common/ClientSelect";
import { FileDropzone } from "@/components/common/FileDropzone";
import { IsolationBadge } from "@/components/trust/TrustSignals";
import { LedgerMatrix } from "./LedgerMatrix";
import { PlatformPicker, RatePresets } from "./SplitterControls";

export const SplitterPanel = ({ clients, onConverted }) => {
  const [clientId, setClientId] = useState("");
  const [platform, setPlatform] = useState("doordash");
  const [rate, setRate] = useState("30");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [payout, setPayout] = useState(null);
  const lastRate = useRef(null);
  const meta = platformMeta(platform);

  const choosePlatform = (id) => {
    setPlatform(id);
    setRate(platformMeta(id).defaultRate);
  };

  useEffect(() => {
    if (!clientId && clients.length) setClientId(clients[0].id);
  }, [clients, clientId]);

  useEffect(() => {
    const r = Number(rate);
    if (!payout || platformMeta(payout.platform).fileFees || rate === "" || r < 0 || r > 100 || r === lastRate.current) return;
    const t = setTimeout(async () => {
      try {
        const { data } = await api.post(`/payouts/${payout.id}/recalculate`, { commission_rate: r });
        lastRate.current = r;
        setPayout(data);
      } catch (e) {
        toast.error(errMsg(e));
      }
    }, 350);
    return () => clearTimeout(t);
  }, [rate, payout]);

  const submit = async () => {
    if (!clientId) return toast.error("Select a client profile first");
    if (!file) return toast.error("Upload a platform payout CSV first");
    const r = Number(rate);
    if (rate === "" || r < 0 || r > 100) return toast.error("Commission rate must be between 0 and 100");
    setLoading(true);
    const form = new FormData();
    form.append("file", file);
    form.append("client_id", clientId);
    form.append("platform", platform);
    form.append("commission_rate", String(r));
    try {
      const { data } = await api.post("/payouts", form);
      lastRate.current = r;
      setPayout(data);
      onConverted?.();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setPayout(null); setFile(null); lastRate.current = null; };
  const sample = () => downloadFile(`/payouts/sample/${platform}`, `sample_${platform}_payout.csv`).catch((e) => toast.error(errMsg(e)));
  const qbo = () => downloadFile(`/payouts/${payout.id}/qbo`, `qbo_journal_${payout.platform}_${payout.id.slice(-6)}.csv`).catch((e) => toast.error(errMsg(e)));

  return (
    <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]" data-testid="splitter-panel">
      <div className="space-y-5">
        <div>
          <label className="text-xs uppercase tracking-wider text-slate-400">Client profile</label>
          <div className="mt-2"><ClientSelect clients={clients} value={clientId} onChange={setClientId} testId="splitter-client-select" /></div>
        </div>
        <PlatformPicker value={platform} onChange={choosePlatform} disabled={!!payout} />
        {meta.fileFees ? (
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-400" data-testid="file-fees-note">
            <span className="text-slate-200 font-medium">Fees come from the file.</span> Each transaction's fee is read from the CSV fee column and summed, so no rate is needed.
          </div>
        ) : (
        <div>
          <label htmlFor="commission-rate" className="text-xs uppercase tracking-wider text-slate-400">Platform Commission Rate %</label>
          <div className="mt-2 flex items-center gap-3">
            <Input id="commission-rate" type="number" min="0" max="100" step="0.1" value={rate} onChange={(e) => setRate(e.target.value)} className="h-11 w-28 num bg-slate-950/50 border-slate-700" data-testid="commission-rate-input" />
            <RatePresets value={rate} onChange={setRate} presets={meta.presets} />
          </div>
        </div>
        )}
        {!payout && (
          <div>
            <FileDropzone accept=".csv" title="Drop platform payout CSV" hint="Toast, DoorDash, UberEats, Shopify, Stripe or LawPay export" onFile={setFile} selectedName={file?.name} testId="payout-upload-dropzone" />
            <IsolationBadge testId="splitter-isolation-badge" />
            <button onClick={sample} className="mt-3 text-xs font-medium text-emerald-400 hover:text-emerald-300" data-testid="download-sample-csv-button">
              Download a sample {meta.name} CSV
            </button>
          </div>
        )}
        {payout ? (
          <Button variant="outline" onClick={reset} className="w-full h-11 border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800" data-testid="split-another-button">
            <RotateCcw className="h-4 w-4 mr-1.5" />Split another payout
          </Button>
        ) : (
          <Button onClick={submit} disabled={loading} className="w-full h-11 bg-slate-100 text-slate-900 hover:bg-white font-semibold" data-testid="calculate-ledger-button">
            {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Calculator className="h-4 w-4 mr-2" />}Calculate journal entry
          </Button>
        )}
      </div>
      <div className="space-y-4 min-w-0">
        {payout ? (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm" data-testid="payout-detection-summary">
              <div className="surface px-4 py-3"><div className="text-[11px] uppercase tracking-wider text-slate-500">Rows parsed</div><div className="num mt-1 text-slate-100" data-testid="payout-rows-parsed">{payout.rows_parsed}</div></div>
              <div className="surface px-4 py-3"><div className="text-[11px] uppercase tracking-wider text-slate-500">Gross column</div><div className="mt-1 truncate text-slate-100" data-testid="payout-gross-column">{payout.gross_column}</div></div>
              <div className="surface px-4 py-3"><div className="text-[11px] uppercase tracking-wider text-slate-500">Gross sales</div><div className="num mt-1 text-emerald-300" data-testid="payout-gross-total">{money(payout.gross_total)}</div></div>
              {platformMeta(payout.platform).fileFees ? (
                <div className="surface px-4 py-3"><div className="text-[11px] uppercase tracking-wider text-slate-500">Fees per file</div><div className="num mt-1 text-slate-100" data-testid="payout-file-fees">{money(payout.fee_total)}</div><div className="text-[11px] text-slate-500 truncate">{payout.fee_line_items} line items · {payout.fee_column}</div></div>
              ) : (
                <div className="surface px-4 py-3"><div className="text-[11px] uppercase tracking-wider text-slate-500">Net per file</div><div className="num mt-1 text-slate-100" data-testid="payout-file-net">{payout.file_net_total == null ? "Not found" : money(payout.file_net_total)}</div></div>
              )}
            </div>
            <LedgerMatrix ledger={payout.ledger} />
            <Button onClick={qbo} disabled={!payout.ledger.balanced} className="h-11 bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold" data-testid="download-qbo-csv-button">
              <Download className="h-4 w-4 mr-2" />Download QuickBooks Journal Entry CSV
            </Button>
          </>
        ) : (
          <div className="h-full min-h-[280px] rounded-xl border border-dashed border-slate-800 flex flex-col items-center justify-center text-center p-8" data-testid="ledger-empty-state">
            <div className="flex flex-wrap justify-center gap-2 text-[10px] uppercase tracking-wider text-slate-500 mb-4" data-testid="ledger-empty-accounts">
              {meta.ledger.map((a) => <span key={a} className="rounded border border-slate-800 px-2 py-1">{a}</span>)}
            </div>
            <p className="text-slate-300 font-medium">Your balanced journal entry appears here</p>
            <p className="mt-1 text-sm text-slate-500 max-w-sm">
              {meta.id === "lawpay"
                ? "Upload a LawPay deposit export. The full deposit stays in trust and processing fees are charged to your operating account."
                : "Upload a platform statement and we will split gross sales into net cash and commission expense."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
