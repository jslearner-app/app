import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/context/AuthContext";
import { errMsg } from "@/lib/api";
import { Brand } from "@/components/common/Brand";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { CaseStudyReviews, SecurityStrip } from "@/components/trust/TrustSignals";

const Field = ({ id, label, ...props }) => (
  <div className="space-y-1.5">
    <Label htmlFor={id} className="text-slate-300 text-xs uppercase tracking-wider">{label}</Label>
    <Input id={id} className="h-11 bg-slate-950/50 border-slate-700" data-testid={`auth-${id}-input`} {...props} />
  </div>
);

export default function AuthPage({ mode }) {
  const isLogin = mode === "login";
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", firm_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (isLogin) await login(form.email, form.password);
      else await register(form);
      navigate("/dashboard");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="flex flex-col px-6 sm:px-12 py-8">
        <Brand />
        <div className="flex-1 flex items-center">
          <form onSubmit={submit} className="w-full max-w-sm space-y-5 reveal" data-testid={`${mode}-form`}>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50">{isLogin ? "Sign in to your workspace" : "Start your free trial"}</h1>
              <p className="mt-2 text-sm text-slate-400">{isLogin ? "Welcome back. Your client books are waiting." : "5 free statement pages. No credit card required."}</p>
            </div>
            <GoogleButton />
            <div className="flex items-center gap-3 text-xs text-slate-500"><span className="h-px flex-1 bg-slate-800" />or with email<span className="h-px flex-1 bg-slate-800" /></div>
            {!isLogin && <Field id="name" label="Full name" value={form.name} onChange={set("name")} required />}
            {!isLogin && <Field id="firm" label="Firm name (optional)" value={form.firm_name} onChange={set("firm_name")} />}
            <Field id="email" label="Work email" type="email" value={form.email} onChange={set("email")} required autoComplete="email" />
            <Field id="password" label="Password" type="password" value={form.password} onChange={set("password")} required minLength={isLogin ? 1 : 8} autoComplete={isLogin ? "current-password" : "new-password"} />
            {error && <p className="text-sm text-rose-400" data-testid="auth-error-message">{error}</p>}
            <Button type="submit" disabled={busy} className="w-full h-11 bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold" data-testid="auth-submit-button">
              {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}{isLogin ? "Sign in" : "Create account"}
            </Button>
            <p className="text-sm text-slate-400">
              {isLogin ? "New to LedgerStream AI? " : "Already have an account? "}
              <Link to={isLogin ? "/register" : "/login"} className="text-emerald-400 hover:text-emerald-300 font-medium" data-testid="auth-switch-link">
                {isLogin ? "Create an account" : "Sign in"}
              </Link>
            </p>
          </form>
        </div>
      </div>
      <div className="hidden lg:flex flex-col justify-center gap-8 bg-[#080e21] border-l border-slate-800 p-12 relative noise grid-bg">
        <div className="relative">
          <div className="eyebrow mb-3">Trusted by bookkeeping firms</div>
          <h2 className="text-2xl font-semibold text-slate-50 max-w-md">From backlog to balanced books in minutes.</h2>
        </div>
        <div className="relative"><CaseStudyReviews compact /></div>
        <div className="relative"><SecurityStrip /></div>
      </div>
    </div>
  );
}
