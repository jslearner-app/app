import { useState } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errMsg } from "@/lib/api";
import { AuthShell } from "@/components/auth/AuthShell";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a link to choose a new password." testId="forgot-password-page">
      {sent ? (
        <p className="rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-200" data-testid="forgot-sent-message">
          If an account exists for {email}, a reset link is on its way. It expires in 1 hour.
        </p>
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="forgot-email" className="text-slate-300 text-xs uppercase tracking-wider">Work email</Label>
            <Input id="forgot-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-11 bg-slate-950/50 border-slate-700" data-testid="forgot-email-input" />
          </div>
          {error && <p className="text-sm text-rose-400" data-testid="forgot-error-message">{error}</p>}
          <Button type="submit" disabled={busy} className="w-full h-11 bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold" data-testid="forgot-submit-button">
            {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Send reset link
          </Button>
        </form>
      )}
      <Link to="/login" className="block text-sm text-emerald-400 hover:text-emerald-300 font-medium" data-testid="forgot-back-to-login-link">Back to sign in</Link>
    </AuthShell>
  );
}
