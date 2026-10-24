import { PLATFORMS } from "@/lib/format";

export const PlatformPicker = ({ value, onChange, disabled }) => (
  <div>
    <div className="text-xs uppercase tracking-wider text-slate-400">Platform statement</div>
    <div className="mt-2 grid grid-cols-3 sm:grid-cols-6 xl:grid-cols-3 gap-2" data-testid="platform-picker">
      {PLATFORMS.map((p) => (
        <button
          key={p.id}
          type="button"
          disabled={disabled}
          onClick={() => onChange(p.id)}
          data-testid={`platform-option-${p.id}`}
          className={`flex flex-col items-center gap-1.5 rounded-lg border px-2 py-2.5 text-xs font-medium transition-colors ${
            value === p.id ? "border-emerald-500 bg-emerald-500/10 text-emerald-200" : "border-slate-700 text-slate-300 hover:border-slate-500"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <img src={p.logo} alt="" width="18" height="18" className="h-[18px] w-[18px]" />
          {p.name}
        </button>
      ))}
    </div>
  </div>
);

export const RatePresets = ({ value, onChange, presets }) => (
  <div className="flex flex-wrap gap-1.5">
    {presets.map((p) => (
      <button
        key={p}
        type="button"
        onClick={() => onChange(p)}
        data-testid={`rate-preset-${p}`}
        className={`num rounded-md border px-2.5 py-1.5 text-xs transition-colors ${
          String(value) === p ? "border-emerald-500 bg-emerald-500/10 text-emerald-200" : "border-slate-700 text-slate-400 hover:text-slate-200"
        }`}
      >
        {p}%
      </button>
    ))}
  </div>
);
