import { Brand } from "@/components/common/Brand";

export const AuthShell = ({ title, subtitle, children, testId }) => (
  <div className="min-h-screen flex flex-col px-6 sm:px-12 py-8">
    <Brand />
    <div className="flex-1 flex items-center justify-center">
      <div className="w-full max-w-sm space-y-5 reveal" data-testid={testId}>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50">{title}</h1>
          <p className="mt-2 text-sm text-slate-400">{subtitle}</p>
        </div>
        {children}
      </div>
    </div>
  </div>
);
