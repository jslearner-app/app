import { useEffect } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Briefcase, Clock, Mail } from "lucide-react";
import { Brand } from "@/components/common/Brand";
import { useAuth } from "@/context/AuthContext";
import { ContactForm } from "@/components/contact/ContactForm";

const CHANNELS = [
  {
    id: "support",
    icon: Mail,
    title: "General Support & Engineering Teams",
    text: "For technical assistance, API key setup queries, or feedback regarding your private alpha testing access, reach out directly to our engineering workspace desk.",
    email: "support@ledgerstreamai.com",
    sla: "Assured review and engineer follow-up within 12 business hours.",
  },
  {
    id: "sales",
    icon: Briefcase,
    title: "Enterprise & Firm Sales Desk",
    text: "If you manage an accounting agency with custom dataset processing targets exceeding 1,000 pages per month, or require dedicated firm deployment parameters, connect with our partnership team.",
    email: "sales@ledgerstreamai.com",
    sla: "Custom pricing models and processing quotes delivered within 1 business day.",
  },
];

const ChannelCard = ({ c, i }) => (
  <article className="surface p-6 sm:p-8 flex flex-col reveal" style={{ animationDelay: `${100 + i * 90}ms` }} data-testid={`contact-channel-${c.id}`}>
    <span className="h-11 w-11 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
      <c.icon className="h-5 w-5 text-emerald-400" aria-hidden="true" />
    </span>
    <h3 className="mt-5 text-lg sm:text-xl font-semibold text-slate-50">{c.title}</h3>
    <p className="mt-2 text-sm sm:text-base text-slate-400 leading-relaxed flex-1">{c.text}</p>
    <dl className="mt-6 space-y-3 border-t border-slate-800 pt-5 text-sm">
      <div>
        <dt className="text-[11px] uppercase tracking-wider text-slate-500">Email Contact</dt>
        <dd className="mt-1">
          <a href={`mailto:${c.email}`} className="font-mono text-emerald-300 hover:text-emerald-200 break-all" data-testid={`contact-email-${c.id}`}>{c.email}</a>
        </dd>
      </div>
      <div>
        <dt className="text-[11px] uppercase tracking-wider text-slate-500">Response Framework</dt>
        <dd className="mt-1 flex items-start gap-2 text-slate-300"><Clock className="h-4 w-4 mt-0.5 text-slate-500 shrink-0" />{c.sla}</dd>
      </div>
    </dl>
  </article>
);

export default function Contact() {
  const { user } = useAuth();
  useEffect(() => {
    document.title = "Contact LedgerStream AI Support & Sales";
  }, []);

  return (
    <div className="min-h-screen bg-background" data-testid="contact-page">
      <header className="border-b border-slate-800/70 bg-[#0b132b]/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto h-16 px-5 sm:px-8 flex items-center justify-between">
          <Brand />
          <Link to={user ? "/dashboard" : "/"} className="inline-flex items-center gap-1.5 text-sm text-slate-300 hover:text-white" data-testid="contact-back-link">
            <ArrowLeft className="h-4 w-4" />{user ? "Back to dashboard" : "Back to home"}
          </Link>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-5 sm:px-8 py-14 sm:py-20">
        <div className="max-w-2xl reveal">
          <div className="eyebrow mb-3">Support & Sales</div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-slate-50">Contact LedgerStream AI Support & Sales</h1>
          <p className="mt-4 text-base sm:text-lg text-slate-400">
            We are here to support your bookkeeping and accounting firm automation workflows. Choose the direct communication channel below that best fits your immediate operational needs.
          </p>
        </div>
        <h2 className="mt-12 mb-5 text-base md:text-lg font-semibold text-slate-200">Direct Channels</h2>
        <div className="grid gap-5 md:grid-cols-2">
          {CHANNELS.map((c, i) => <ChannelCard key={c.id} c={c} i={i} />)}
        </div>
        <section className="mt-14 max-w-3xl" data-testid="contact-form-section">
          <h2 className="mb-2 text-base md:text-lg font-semibold text-slate-200">Send us a message</h2>
          {user ? (
            <ContactForm />
          ) : (
            <div className="surface p-6 text-sm text-slate-400" data-testid="contact-form-signin-prompt">
              <Link to="/login" className="font-medium text-emerald-400 hover:text-emerald-300">Sign in</Link> to send a message from your account, or email the desks above directly.
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
