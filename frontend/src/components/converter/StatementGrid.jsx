import { useMemo, useState } from "react";
import { ArrowUpDown, ChevronDown, Download, Pencil, Save, Search, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { api, downloadFile, errMsg } from "@/lib/api";
import { money } from "@/lib/format";
import { notifyHistoryChanged } from "@/hooks/useReviewCount";

const COLS = [
  { key: "date", label: "Date" },
  { key: "description", label: "Description" },
  { key: "reference", label: "Reference/Check #" },
  { key: "withdrawal", label: "Withdrawals", num: true },
  { key: "deposit", label: "Deposits", num: true },
  { key: "balance", label: "Balance", num: true },
];

const sortValue = (row, key) => (key === "date" ? new Date(row.date).getTime() || 0 : row[key] ?? "");

export const StatementGrid = ({ statement, onSaved }) => {
  const [rows, setRows] = useState(statement.rows);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = q ? rows.filter((r) => `${r.date} ${r.description} ${r.reference}`.toLowerCase().includes(q)) : rows;
    if (sort) {
      list = [...list].sort((a, b) => {
        const av = sortValue(a, sort.key), bv = sortValue(b, sort.key);
        return (av > bv ? 1 : av < bv ? -1 : 0) * sort.dir;
      });
    }
    return list;
  }, [rows, query, sort]);

  const flagged = useMemo(
    () => new Set((statement.summary?.reconciliation?.mismatched_rows || []).map((m) => m.id)),
    [statement.summary]
  );

  const updateCell = (id, key, value, num) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, [key]: num ? (value === "" ? null : Number(value)) : value } : r)));

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.put(`/statements/${statement.id}/rows`, { rows });
      setRows(data.rows);
      onSaved(data);
      notifyHistoryChanged();
      setEditing(false);
      toast.success("Changes saved");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => { setRows(statement.rows); setEditing(false); };
  const base = statement.filename.replace(/\.pdf$/i, "");
  const exportAs = (fmt) =>
    downloadFile(`/statements/${statement.id}/export?fmt=${fmt}`, `${base}_ledger.${fmt}`).catch((e) => toast.error(errMsg(e)));

  return (
    <div className="surface overflow-hidden" data-testid="statement-data-grid">
      <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter transactions" className="pl-9 h-10 bg-slate-950/50 border-slate-700" data-testid="grid-search-input" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <Button variant="ghost" onClick={cancel} data-testid="grid-cancel-edit-button" className="text-slate-300"><X className="h-4 w-4 mr-1" />Cancel</Button>
              <Button onClick={save} disabled={saving} data-testid="grid-save-button" className="bg-slate-100 text-slate-900 hover:bg-white"><Save className="h-4 w-4 mr-1" />Save changes</Button>
            </>
          ) : (
            <Button variant="outline" onClick={() => setEditing(true)} data-testid="grid-edit-button" className="border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800"><Pencil className="h-4 w-4 mr-1" />Edit rows</Button>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button disabled={editing} data-testid="export-accounting-button" className="bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold">
                <Download className="h-4 w-4 mr-1.5" />Export to Accounting Excel/CSV<ChevronDown className="h-4 w-4 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => exportAs("xlsx")} data-testid="export-xlsx-option">Excel workbook (.xlsx)</DropdownMenuItem>
              <DropdownMenuItem onClick={() => exportAs("csv")} data-testid="export-csv-option">CSV file (.csv)</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <div className="overflow-auto max-h-[560px]">
        <table className="w-full text-sm border-collapse min-w-[760px]">
          <thead className="sticky top-0 z-10 bg-[#16203a]">
            <tr>
              {COLS.map((c) => (
                <th key={c.key} className={`px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-700 ${c.num ? "text-right" : "text-left"}`}>
                  <button
                    onClick={() => setSort((s) => ({ key: c.key, dir: s?.key === c.key ? -s.dir : 1 }))}
                    className="inline-flex items-center gap-1 hover:text-slate-200"
                    data-testid={`grid-sort-${c.key}`}
                  >
                    {c.label}<ArrowUpDown className="h-3 w-3" />
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr
                key={r.id}
                className={`border-b border-slate-800/70 transition-colors ${flagged.has(r.id) ? "bg-amber-500/10 hover:bg-amber-500/15 shadow-[inset_3px_0_0_#fbbf24]" : "hover:bg-slate-800/30"}`}
                data-testid={`grid-row-${r.id}`}
                data-mismatch={flagged.has(r.id) ? "true" : undefined}
              >
                {COLS.map((c) => (
                  <td key={c.key} className={`px-4 py-2.5 ${c.num ? "text-right num" : ""} ${c.key === "description" ? "text-slate-100" : "text-slate-300"}`}>
                    {editing ? (
                      <input
                        value={r[c.key] ?? ""}
                        type={c.num ? "number" : "text"}
                        step="0.01"
                        onChange={(e) => updateCell(r.id, c.key, e.target.value, c.num)}
                        className={`w-full min-w-[80px] bg-slate-950/70 border border-slate-700 rounded px-2 py-1 text-sm focus:border-emerald-500 outline-none ${c.num ? "text-right num" : ""}`}
                        data-testid={`grid-cell-input-${r.id}-${c.key}`}
                      />
                    ) : c.num ? (
                      <span className={c.key === "withdrawal" && r[c.key] ? "text-rose-300" : c.key === "deposit" && r[c.key] ? "text-emerald-300" : ""}>
                        {r[c.key] == null ? "" : money(r[c.key])}
                      </span>
                    ) : (
                      r[c.key] || <span className="text-slate-600">—</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
            {!visible.length && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-500">No transactions match your filter.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
