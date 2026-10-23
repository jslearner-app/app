import { useCallback, useEffect, useState } from "react";
import { FileSpreadsheet, Scale } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useClients } from "@/hooks/useClients";
import { PageHeader } from "@/components/common/PageHeader";
import { ConverterPanel } from "@/components/converter/ConverterPanel";
import { SplitterPanel } from "@/components/splitter/SplitterPanel";
import { OnboardingTrust } from "@/components/dashboard/OnboardingTrust";

const Metric = ({ label, value, testId }) => (
  <div className="surface p-5">
    <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
    <div className="mt-2 num text-2xl sm:text-3xl font-semibold text-slate-50" data-testid={testId}>{value}</div>
  </div>
);

const TabCard = ({ value, icon: Icon, title, sub }) => (
  <TabsTrigger
    value={value}
    data-testid={`module-tab-${value}`}
    className="flex-1 justify-start gap-3 rounded-lg border border-slate-800 bg-slate-900/50 px-4 py-3.5 text-left data-[state=active]:border-emerald-500/60 data-[state=active]:bg-emerald-500/10 data-[state=active]:shadow-none"
  >
    <Icon className="h-5 w-5 text-emerald-400 shrink-0" />
    <span className="min-w-0">
      <span className="block font-display font-semibold text-slate-100 text-sm sm:text-base">{title}</span>
      <span className="hidden sm:block text-xs text-slate-400 font-normal truncate">{sub}</span>
    </span>
  </TabsTrigger>
);

export default function Dashboard() {
  const { user } = useAuth();
  const { clients } = useClients();
  const [summary, setSummary] = useState(null);

  const loadSummary = useCallback(() => {
    api.get("/dashboard/summary").then(({ data }) => setSummary(data)).catch(() => {});
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const isNew = summary && summary.statements + summary.payouts === 0;
  const first = (user.name || "").split(" ")[0];

  return (
    <div data-testid="dashboard-page">
      <PageHeader eyebrow="Workspace" title={first ? `Welcome back, ${first}` : "Welcome back"} description="Convert bank statements and split merchant payouts into balanced, export-ready books." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-8">
        <Metric label="Client accounts" value={summary?.clients ?? "–"} testId="metric-clients" />
        <Metric label="Statements converted" value={summary?.statements ?? "–"} testId="metric-statements" />
        <Metric label="Transactions extracted" value={summary?.transactions_extracted ?? "–"} testId="metric-transactions" />
        <Metric label="Payouts split" value={summary?.payouts ?? "–"} testId="metric-payouts" />
      </div>
      {isNew && <OnboardingTrust />}
      <Tabs defaultValue="converter" className="w-full">
        <TabsList className="h-auto w-full bg-transparent p-0 gap-3 flex flex-col sm:flex-row mb-6">
          <TabCard value="converter" icon={FileSpreadsheet} title="Bank Statement Converter" sub="PDF statements to a clean transaction ledger" />
          <TabCard value="splitter" icon={Scale} title="Merchant Payout Splitter" sub="Platform payouts to a balanced QBO journal entry" />
        </TabsList>
        <TabsContent value="converter" className="mt-0">
          <ConverterPanel clients={clients} onConverted={loadSummary} />
        </TabsContent>
        <TabsContent value="splitter" className="mt-0">
          <SplitterPanel clients={clients} onConverted={loadSummary} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
