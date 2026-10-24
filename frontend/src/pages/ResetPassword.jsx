import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errMsg } from "@/lib/api";
import { AuthShell } from "@/components/auth/AuthShell";

const PasswordField = ({ id, label, ...props }) => (
  <div className="space-y-1.5">
    <Label htmlFor={id} className="text-slate-300 text-xs uppercase tracking-wider">{label}</Label>
    <Input id={id} type="password" required minLength={8} autoComplete="new-password" className="h-11 bg-slate-950/50 border-slate-700" data-testid={`${id}-input`} {...props} />
  </div>
);

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [form, setForm] = useState({ password: "", confirm: "" });
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (form.password !== form.confirm) return setError("Passwords don't match.");
    setError("");
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, password: form.password });
      setDone(true);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  const body = !token ? (
    <p className="text-sm text-rose-400" data-testid="reset-invalid-message">This reset link is invalid. Request a new one.</p>
  ) : done ? (
    <p className="rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-200" data-testid="reset-success-message">Your password has been updated. You can sign in now.</p>
  ) : (
    <form onSubmit={submit} className="space-y-5">
      <PasswordField id="reset-password" label="New password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
      <PasswordField id="reset-password-confirm" label="Confirm password" value={form.confirm} onChange={(e) => setForm((f) => ({ ...f, confirm: e.target.value }))} />
      {error && <p className="text-sm text-rose-400" data-testid="reset-error-message">{error}</p>}
      <Button type="submit" disabled={busy} className="w-full h-11 bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold" data-testid="reset-submit-button">
        {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Update password
      </Button>
    </form>
  );

  return (
    <AuthShell title="Choose a new password" subtitle="Use at least 8 characters." testId="reset-password-page">
      {body}
      <Link to={done ? "/login" : "/forgot-password"} className="block text-sm text-emerald-400 hover:text-emerald-300 font-medium" data-testid="reset-footer-link">
        {done ? "Go to sign in" : "Request a new link"}
      </Link>
    </AuthShell>
  );
}
