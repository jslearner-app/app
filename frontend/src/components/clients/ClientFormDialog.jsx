import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { api, errMsg } from "@/lib/api";
import { PLATFORMS } from "@/lib/format";

const EMPTY = { name: "", industry: "", contact_email: "", platforms: [], notes: "" };

export const ClientFormDialog = ({ client, onClose, onSaved }) => {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const isEdit = !!client?.id;

  useEffect(() => {
    if (client) setForm({ ...EMPTY, ...client });
  }, [client]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const toggle = (p) => setForm((f) => ({ ...f, platforms: f.platforms.includes(p) ? f.platforms.filter((x) => x !== p) : [...f.platforms, p] }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const payload = { name: form.name, industry: form.industry, contact_email: form.contact_email, platforms: form.platforms, notes: form.notes };
    try {
      if (isEdit) await api.put(`/clients/${client.id}`, payload);
      else await api.post("/clients", payload);
      toast.success(isEdit ? "Client updated" : "Client created");
      onSaved();
      onClose();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={!!client} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-[#0f1830] border-slate-800 max-w-lg" data-testid="client-form-dialog">
        <DialogHeader><DialogTitle className="font-display">{isEdit ? "Edit client" : "New client profile"}</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="client-name">Business name</Label>
            <Input id="client-name" value={form.name} onChange={set("name")} required placeholder="The Burger Shack" className="bg-slate-950/50 border-slate-700" data-testid="client-name-input" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="client-industry">Industry</Label>
              <Input id="client-industry" value={form.industry} onChange={set("industry")} placeholder="Restaurant" className="bg-slate-950/50 border-slate-700" data-testid="client-industry-input" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="client-email">Contact email</Label>
              <Input id="client-email" type="email" value={form.contact_email} onChange={set("contact_email")} className="bg-slate-950/50 border-slate-700" data-testid="client-email-input" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Platforms used</Label>
            <div className="flex flex-wrap gap-2">
              {PLATFORMS.map((p) => (
                <button type="button" key={p.id} onClick={() => toggle(p.id)} data-testid={`client-platform-${p.id}`}
                  className={`rounded-md border px-2.5 py-1.5 text-xs transition-colors ${form.platforms.includes(p.id) ? "border-emerald-500 bg-emerald-500/10 text-emerald-200" : "border-slate-700 text-slate-400 hover:text-slate-200"}`}>
                  {p.name}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="client-notes">Notes</Label>
            <Textarea id="client-notes" value={form.notes} onChange={set("notes")} rows={3} className="bg-slate-950/50 border-slate-700" data-testid="client-notes-input" />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} data-testid="client-form-cancel">Cancel</Button>
            <Button type="submit" disabled={busy} className="bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold" data-testid="client-form-submit">{isEdit ? "Save changes" : "Create client"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
