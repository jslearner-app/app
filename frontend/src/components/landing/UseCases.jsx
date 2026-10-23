import { Link } from "react-router-dom";
import { ArrowRight, FileSpreadsheet, Landmark, Receipt, Scale, Sparkles, UtensilsCrossed } from "lucide-react";

const USE_CASES = [
  {
    id: "pdf-to-excel",
    icon: FileSpreadsheet,
    title: "Convert PDF bank statement to Excel free no email",
    text: "Drop a multi-page bank statement PDF and get clean Date, Description, Reference/Check #, Withdrawals, Deposits and Balance columns in an Excel workbook. Your first 5 pages are free, and Google sign-in takes one click.",
  },
  {
    id: "qbo-restaurant-splitter",
    icon: UtensilsCrossed,
    title: "QuickBooks online restaurant payout splitter",
    text: "Turn restaurant delivery and POS payouts into a balanced journal entry: debit Bank Clearing for net cash, debit Delivery Commissions Expense, credit Gross Sales Revenue. Download a QuickBooks Online import CSV.",
  },
  {
    id: "toast-breakdown",
    icon: Receipt,
    title: "Toast journal entry breakdown tool",
    text: "Upload a Toast export and LedgerStream AI detects the gross sales column, applies your commission rate and balances the entry to the exact penny before export.",
  },
  {
    id: "doordash-parser",
    icon: Scale,
    title: "DoorDash payout CSV parser for bookkeepers",
    text: "DoorDash Subtotal and Net Total columns are recognized automatically. Adjust the platform commission rate and the debits and credits recalculate instantly.",
  },
  {
    id: "lawpay-splitter",
    icon: Landmark,
    title: "LawPay trust account deposit splitter QBO",
    text: "Split law-firm payment deposits into gross receipts and processing fees so every trust account deposit lands in QuickBooks Online as a balanced journal entry.",
  },
  {
    id: "messy-statements",
    icon: Sparkles,
    title: "Clean up messy bank statements PDF to CSV",
    text: "Every converted statement is checked against its running balance. Rows that don't add up are flagged as Needs review, so you can fix them inline and export a clean CSV.",
  },
];

export const UseCases = () => (
  <div className="grid gap-px rounded-2xl overflow-hidden border border-slate-800 bg-slate-800 md:grid-cols-2 lg:grid-cols-3" data-testid="use-cases-grid">
    {USE_CASES.map((u) => (
      <article key={u.id} className="bg-[#0d1630] p-6 sm:p-7 flex flex-col group" data-testid={`use-case-${u.id}`}>
        <u.icon className="h-5 w-5 text-emerald-400" aria-hidden="true" />
        <h3 className="mt-4 text-base sm:text-lg font-semibold text-slate-50 leading-snug">{u.title}</h3>
        <p className="mt-2 text-sm text-slate-400 leading-relaxed flex-1">{u.text}</p>
        <Link to="/register" className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-emerald-400 group-hover:text-emerald-300" data-testid={`use-case-cta-${u.id}`}>
          Try it free <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </article>
    ))}
  </div>
);
