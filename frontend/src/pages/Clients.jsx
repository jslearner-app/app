import { useState } from "react";
import { Building2, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { api, errMsg } from "@/lib/api";
import { platformName } from "@/lib/format";
import { useClients } from "@/hooks/useClients";
import { PageHeader } from "@/components/common/PageHeader";
import { ClientFormDialog } from "@/components/clients/ClientFormDialog";

const ClientCard = ({ c, onEdit, onDelete, index }) => (
  <div className="surface p-5 flex flex-col reveal hover:border-slate-600 transition-colors" style={{ animationDelay: `${index * 50}ms` }} data-testid={`client-card-${c.id}`}>
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-center gap-3 min-w-0">
        <span className="h-10 w-10 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center"><Building2 className="h-5 w-5 text-emerald-400" /></span>
        <div className="min-w-0">
          <div className="font-display font-semibold text-slate-100 truncate" data-testid={`client-name-${c.id}`}>{c.name}</div>
          <div className="text-xs text-slate-400 truncate">{c.industry || "No industry set"}</div>
        </div>
      </div>
      <div className="flex gap-1">
        <button onClick={() => onEdit(c)} className="p-2 rounded-md text-slate-400 hover:text-slate-100 hover:bg-slate-800" data-testid={`client-edit-${c.id}`} aria-label="Edit client"><Pencil className="h-4 w-4" /></button>
        <button onClick={() => onDelete(c)} className="p-2 rounded-md text-slate-400 hover:text-rose-300 hover:bg-slate-800" data-testid={`client-delete-${c.id}`} aria-label="Delete client"><Trash2 className="h-4 w-4" /></button>
      </div>
    </div>
    <div className="mt-4 flex flex-wrap gap-1.5 min-h-[24px]">
      {c.platforms?.map((p) => (
        <span key={p} className="rounded-md border border-slate-700 bg-slate-900 px-2 py-0.5 text-[11px] text-slate-300">{platformName(p)}</span>
      ))}
    </div>
    <div className="mt-5 pt-4 border-t border-slate-800 grid grid-cols-3 gap-2 text-center">
      <div><div className="num text-lg text-slate-50" data-testid={`client-statements-${c.id}`}>{c.statements_count}</div><div className="text-[10px] uppercase tracking-wider text-slate-500">Statements</div></div>
      <div><div className="num text-lg text-slate-50">{c.pages_converted}</div><div className="text-[10px] uppercase tracking-wider text-slate-500">Pages</div></div>
      <div><div className="num text-lg text-slate-50" data-testid={`client-payouts-${c.id}`}>{c.payouts_count}</div><div className="text-[10px] uppercase tracking-wider text-slate-500">Payouts</div></div>
    </div>
  </div>
);

export default function Clients() {
  const { clients, loading, reload } = useClients();
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const confirmDelete = async () => {
    try {
      await api.delete(`/clients/${deleting.id}`);
      toast.success(`${deleting.name} removed`);
      reload();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div data-testid="clients-page">
      <PageHeader
        eyebrow="Multi-client workspace"
        title="Client Accounts"
        description="Keep every small business client's statements and payouts in its own profile."
        actions={<Button onClick={() => setEditing({})} className="bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold" data-testid="add-client-button"><Plus className="h-4 w-4 mr-1.5" />Add client</Button>}
      />
      {!loading && !clients.length && (
        <div className="rounded-xl border border-dashed border-slate-700 p-12 text-center" data-testid="clients-empty-state">
          <Building2 className="h-8 w-8 mx-auto text-slate-500" />
          <p className="mt-3 font-medium text-slate-200">No client profiles yet</p>
          <p className="mt-1 text-sm text-slate-500">Add your first client, for example "The Burger Shack".</p>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {clients.map((c, i) => <ClientCard key={c.id} c={c} index={i} onEdit={setEditing} onDelete={setDeleting} />)}
      </div>
      <ClientFormDialog client={editing} onClose={() => setEditing(null)} onSaved={reload} />
      <AlertDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <AlertDialogContent className="bg-[#0f1830] border-slate-800">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleting?.name}?</AlertDialogTitle>
            <AlertDialogDescription>The client profile is removed. Past conversions stay in History.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="client-delete-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-rose-600 hover:bg-rose-500" data-testid="client-delete-confirm">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
