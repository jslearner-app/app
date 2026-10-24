import { useState } from "react";
import { CheckCircle2, Loader2, Send } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const ROLES = [
  { id: "firm_owner", label: "Firm owner / CPA" },
  { id: "staff_bookkeeper", label: "Staff bookkeeper" },
  { id: "freelance_bookkeeper", label: "Freelance bookkeeper" },
  { id: "controller", label: "Controller / finance lead" },
  { id: "other", label: "Other" },
];
const DESKS = [
  { id: "support", label: "Support & Engineering" },
  { id: "sales", label: "Enterprise & Sales" },
];
const field = "bg-slate-950/50 border-slate-700";

export const ContactForm = ({ compact = false }) => {
  const { user } = useAuth();
  const [form, setForm] = useState({ desk: "support", name: user?.name || "", role: "firm_owner", message: "" });
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(null);
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v?.target ? v.target.value : v }));

  const submit = async (e) => {
    e.preventDefault();
    if (form.message.trim().length < 10) return toast.error("Please write at least 10 characters");
    setBusy(true);
    try {
      await api.post("/contact", form);
      setSent(form.desk);
      setForm((f) => ({ ...f, message: "" }));
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <div className="surface p-6 flex items-start gap-3" data-testid="contact-form-success">
        <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
        <div>
          <div className="font-semibold text-slate-100">Message sent to {DESKS.find((d) => d.id === sent).label}</div>
          <p className="mt-1 text-sm text-slate-400">We'll reply to {user.email}. {sent === "sales" ? "Expect a quote within 1 business day." : "Expect an engineer follow-up within 12 business hours."}</p>
          <button onClick={() => setSent(null)} className="mt-3 text-sm font-medium text-emerald-400 hover:text-emerald-300" data-testid="contact-form-send-another">Send another message</button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className={`surface ${compact ? "p-5" : "p-6 sm:p-8"} space-y-4`} data-testid="contact-form">
      <div className="inline-flex rounded-lg border border-slate-800 bg-slate-900/50 p-1" role="radiogroup" aria-label="Desk">
        {DESKS.map((d) => (
          <button type="button" key={d.id} role="radio" aria-checked={form.desk === d.id} onClick={() => set("desk")(d.id)} data-testid={`contact-desk-${d.id}`}
            className={`px-3 py-1.5 rounded-md text-sm transition-colors ${form.desk === d.id ? "bg-emerald-500/15 text-emerald-200" : "text-slate-400 hover:text-slate-200"}`}>
            {d.label}
          </button>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="contact-name">Name</Label>
          <Input id="contact-name" value={form.name} onChange={set("name")} required maxLength={120} className={field} data-testid="contact-name-input" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="contact-email">Email</Label>
          <Input id="contact-email" value={user.email} readOnly className={`${field} text-slate-400`} data-testid="contact-email-input" />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>Account role</Label>
        <Select value={form.role} onValueChange={set("role")}>
          <SelectTrigger className={`h-10 ${field}`} data-testid="contact-role-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            {ROLES.map((r) => <SelectItem key={r.id} value={r.id} data-testid={`contact-role-${r.id}`}>{r.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="contact-message">Message</Label>
        <Textarea id="contact-message" value={form.message} onChange={set("message")} rows={compact ? 4 : 5} maxLength={4000} required
          placeholder={form.desk === "sales" ? "Tell us about your firm and monthly page volume..." : "Describe the issue or question..."} className={field} data-testid="contact-message-input" />
      </div>
      <Button type="submit" disabled={busy} className="bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold" data-testid="contact-submit-button">
        {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />}Send message
      </Button>
    </form>
  );
};
