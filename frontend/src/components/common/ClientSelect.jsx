import { Link } from "react-router-dom";
import { Building2 } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const ClientSelect = ({ clients, value, onChange, testId }) => {
  if (!clients.length) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm" data-testid={`${testId}-empty`}>
        <span className="text-amber-200">No client profiles yet.</span>
        <Link to="/clients" className="font-medium text-emerald-400 hover:text-emerald-300" data-testid={`${testId}-create-link`}>
          Create a client
        </Link>
      </div>
    );
  }
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger data-testid={testId} className="h-11 bg-slate-950/50 border-slate-700">
        <div className="flex items-center gap-2">
          <Building2 className="h-4 w-4 text-slate-400" />
          <SelectValue placeholder="Assign to client profile" />
        </div>
      </SelectTrigger>
      <SelectContent>
        {clients.map((c) => (
          <SelectItem key={c.id} value={c.id} data-testid={`${testId}-option-${c.id}`}>
            {c.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};
