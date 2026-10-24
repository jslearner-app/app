import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { api, delay } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const Card = ({ icon, title, text, testId, children }) => (
  <div className="max-w-lg mx-auto mt-10 surface p-8 text-center" data-testid={testId}>
    {icon}
    <h1 className="mt-4 text-2xl font-bold text-slate-50">{title}</h1>
    <p className="mt-2 text-sm text-slate-400">{text}</p>
    <div className="mt-6 flex justify-center gap-3">{children}</div>
  </div>
);

const LinkBtn = ({ to, children, testId }) => (
  <Link to={to} data-testid={testId} className="rounded-lg bg-emerald-500 hover:bg-emerald-400 text-emerald-950 font-semibold px-4 py-2.5 text-sm">{children}</Link>
);

export function PaymentSuccess() {
  const [params] = useSearchParams();
  const { refreshUser } = useAuth();
  const [state, setState] = useState("checking");

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const sessionId = params.get("session_id");
      for (let i = 0; i < 10 && !cancelled; i++) {
        try {
          const { data } = await api.get(`/payments/status/${sessionId}`);
          if (data.payment_status === "paid") {
            await refreshUser();
            if (!cancelled) setState("paid");
            return;
          }
          if (["expired", "failed"].includes(data.payment_status)) break;
        } catch {
          break;
        }
        await delay(2000);
      }
      if (!cancelled) setState("unconfirmed");
    };
    poll();
    return () => { cancelled = true; };
  }, [params, refreshUser]);

  if (state === "checking")
    return <Card testId="payment-checking" icon={<Loader2 className="h-10 w-10 mx-auto animate-spin text-emerald-400" />} title="Confirming your payment" text="This only takes a few seconds." />;
  if (state === "paid")
    return (
      <Card testId="payment-success" icon={<CheckCircle2 className="h-10 w-10 mx-auto text-emerald-400" />} title="Subscription active" text="Your monthly parsed-page allowance is now active for your firm.">
        <LinkBtn to="/dashboard" testId="payment-success-dashboard-link">Go to dashboard</LinkBtn>
      </Card>
    );
  return (
    <Card testId="payment-unconfirmed" icon={<XCircle className="h-10 w-10 mx-auto text-amber-300" />} title="Payment not confirmed yet" text="We couldn't confirm this payment. If you were charged, refresh in a minute or check Billing.">
      <LinkBtn to="/billing" testId="payment-unconfirmed-billing-link">Go to billing</LinkBtn>
    </Card>
  );
}

export function PaymentCancel() {
  return (
    <Card testId="payment-cancel" icon={<XCircle className="h-10 w-10 mx-auto text-slate-400" />} title="Checkout cancelled" text="No charge was made. You can pick a plan whenever you're ready.">
      <LinkBtn to="/pricing" testId="payment-cancel-pricing-link">Back to pricing</LinkBtn>
    </Card>
  );
}
