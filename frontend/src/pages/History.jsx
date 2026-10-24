import { useCallback, useEffect, useState } from "react";
import { Download, FileSpreadsheet, Scale, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, downloadFile, errMsg } from "@/lib/api";
import { money, platformName, shortDate } from "@/lib/format";
import { useClients } from "@/hooks/useClients";
import { notifyHistoryChanged, useReviewCount } from "@/hooks/useReviewCount";
import { PageHeader } from "@/components/common/PageHeader";

const KINDS = [{ id: "all", label: "All" }, { id: "statement", label: "Statements" }, { id: "payout", label: "Payouts" }, { id: "needs_review", label: "Needs review" }];

const exportItem = (it) =>
  (it.kind === "statement"
    ? downloadFile(`/statements/${it.id}/export?fmt=xlsx`, `${it.filename.replace(/\.pdf$/i, "")}_ledger.xlsx`)
    : downloadFile(`/payouts/${it.id}/qbo`, `qbo_journal_${it.platform}_${it.id.slice(-6)}.csv`)
  ).catch((e) => toast.error(errMsg(e)));

const REC_BADGES = {
  reconciled: { label: "Reconciled", cls: "border-emerald-500/40 bg-emerald-950 text-emerald-300" },
  mismatch: { label: "Needs review", cls: "border-amber-500/40 bg-amber-950 text-amber-300" },
  unavailable: { label: "No balance column", cls: "border-slate-700 bg-slate-900 text-slate-400" },
};

const RecBadge = ({ it }) => {
  const status = it.kind === "statement" ? it.summary?.reconciliation?.status : null;
  const badge = REC_BADGES[status];
  if (!badge) return <span className="text-slate-600">—</span>;
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold whitespace-nowrap ${badge.cls}`} data-testid={`history-rec-badge-${it.id}`} data-status={status}>
      {badge.label}
    </span>
  );
};

const Details = ({ it }) =>
  it.kind === "statement" ? (
    <span>{it.pages} page(s) · {it.summary?.transactions} txns</span>
  ) : (
    <span>{platformName(it.platform)} · {money(it.gross_total)} gross {it.fee_column && it.platform === "lawpay" ? `· ${money(it.fee_total)} fees from file` : `@ ${it.commission_rate}%`}</span>
  );

export default function History() {
  const { clients } = useClients();
  const [clientId, setClientId] = useState("all");
  const [kind, setKind] = useState("all");
  const [items, setItems] = useState(null);
  const reviewCount = useReviewCount();

  const load = useCallback(async () => {
    const params = {};
    if (clientId !== "all") params.client_id = clientId;
    if (kind !== "all") params.kind = kind;
    try {
      const { data } = await api.get("/history", { params });
      setItems(data);
    } catch (e) {
      toast.error(errMsg(e));
    }
  }, [clientId, kind]);

  useEffect(() => {
    load();
  }, [load]);

  const remove = async (it) => {
    try {
      await api.delete(`/history/${it.kind}/${it.id}`);
      toast.success("Removed from history");
      load();
      notifyHistoryChanged();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <div data-testid="history-page">
      <PageHeader eyebrow="Audit trail" title="History" description="Every statement conversion and payout split, ready to re-export." />
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="inline-flex max-w-full overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/50 p-1">
          {KINDS.map((k) => (
            <button key={k.id} onClick={() => setKind(k.id)} data-testid={`history-filter-${k.id}`}
              className={`inline-flex items-center gap-1.5 whitespace-nowrap px-3 py-1.5 rounded-md text-sm transition-colors ${kind === k.id ? "bg-slate-800 text-slate-50" : "text-slate-400 hover:text-slate-200"}`}>
              {k.label}
              {k.id === "needs_review" && reviewCount > 0 && (
                <span className="rounded-full bg-amber-400/15 border border-amber-400/40 px-1.5 text-[11px] font-semibold num text-amber-300" data-testid="history-review-count">{reviewCount}</span>
              )}
            </button>
          ))}
        </div>
        <Select value={clientId} onValueChange={setClientId}>
          <SelectTrigger className="sm:w-64 bg-slate-900/50 border-slate-800" data-testid="history-client-filter"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All clients</SelectItem>
            {clients.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="surface overflow-x-auto">
        <table className="w-full text-sm min-w-[880px]">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-slate-400 bg-[#16203a]">
              <th className="text-left px-4 py-3 font-semibold">Date</th>
              <th className="text-left px-4 py-3 font-semibold">Module</th>
              <th className="text-left px-4 py-3 font-semibold">Client</th>
              <th className="text-left px-4 py-3 font-semibold">File</th>
              <th className="text-left px-4 py-3 font-semibold">Details</th>
              <th className="text-left px-4 py-3 font-semibold">Reconciliation</th>
              <th className="text-right px-4 py-3 font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items?.map((it) => (
              <tr key={it.id} className="border-b border-slate-800/70 hover:bg-slate-800/30" data-testid={`history-row-${it.id}`}>
                <td className="px-4 py-3 text-slate-400 whitespace-nowrap">{shortDate(it.created_at)}</td>
                <td className="px-4 py-3 text-slate-200 whitespace-nowrap">
                  {it.kind === "statement" ? <FileSpreadsheet className="inline h-4 w-4 mr-1.5 text-emerald-400" /> : <Scale className="inline h-4 w-4 mr-1.5 text-sky-300" />}
                  {it.kind === "statement" ? "Statement" : "Payout split"}
                </td>
                <td className="px-4 py-3 text-slate-200">{it.client_name}</td>
                <td className="px-4 py-3 text-slate-300 max-w-[220px] truncate">{it.filename}</td>
                <td className="px-4 py-3 text-slate-400 num text-xs"><Details it={it} /></td>
                <td className="px-4 py-3"><RecBadge it={it} /></td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <button onClick={() => exportItem(it)} className="p-2 rounded-md text-slate-400 hover:text-emerald-300 hover:bg-slate-800" data-testid={`history-export-${it.id}`} aria-label="Export"><Download className="h-4 w-4" /></button>
                  <button onClick={() => remove(it)} className="p-2 rounded-md text-slate-400 hover:text-rose-300 hover:bg-slate-800" data-testid={`history-delete-${it.id}`} aria-label="Delete"><Trash2 className="h-4 w-4" /></button>
                </td>
              </tr>
            ))}
            {items && !items.length && (
              <tr><td colSpan={7} className="px-4 py-12 text-slate-500" data-testid="history-empty-state"><div className="sticky left-4 max-w-[calc(100vw-5rem)] sm:max-w-none sm:text-center">{kind === "needs_review" ? "No statements need review. Everything reconciles." : "No conversions yet. Head to the Dashboard to process your first file."}</div></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
