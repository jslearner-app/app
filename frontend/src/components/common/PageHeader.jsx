export const PageHeader = ({ eyebrow, title, description, actions, testId }) => (
  <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between mb-8 reveal" data-testid={testId}>
    <div className="max-w-2xl">
      {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
      <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50">{title}</h1>
      {description && <p className="mt-2 text-sm sm:text-base text-slate-400">{description}</p>}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
  </div>
);
