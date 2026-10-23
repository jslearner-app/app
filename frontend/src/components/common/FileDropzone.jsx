import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { toast } from "sonner";

export const FileDropzone = ({ accept, title, hint, onFile, disabled, testId, selectedName }) => {
  const inputRef = useRef(null);
  const [active, setActive] = useState(false);

  const handle = (file) => {
    if (!file || disabled) return;
    if (!file.name.toLowerCase().endsWith(accept)) {
      toast.error(`Please upload a ${accept.toUpperCase().slice(1)} file`);
      return;
    }
    onFile(file);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      data-testid={testId}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setActive(true); }}
      onDragLeave={() => setActive(false)}
      onDrop={(e) => { e.preventDefault(); setActive(false); handle(e.dataTransfer.files?.[0]); }}
      className={`relative rounded-xl border-2 border-dashed p-8 sm:p-10 text-center cursor-pointer transition-colors duration-200 ${
        active ? "border-emerald-500 bg-emerald-950/30" : "border-slate-700 bg-slate-950/40 hover:border-emerald-500/60 hover:bg-slate-900/60"
      } ${disabled ? "opacity-60 cursor-not-allowed" : ""}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        data-testid={`${testId}-input`}
        onChange={(e) => { handle(e.target.files?.[0]); e.target.value = ""; }}
      />
      <div className={`mx-auto mb-4 h-12 w-12 rounded-xl flex items-center justify-center border transition-colors ${active ? "border-emerald-500 bg-emerald-500/15 text-emerald-300" : "border-slate-700 bg-slate-900 text-slate-300"}`}>
        <UploadCloud className="h-6 w-6" />
      </div>
      <p className="font-display font-semibold text-slate-100">{selectedName || title}</p>
      <p className="mt-1 text-sm text-slate-400">{hint}</p>
    </div>
  );
};
