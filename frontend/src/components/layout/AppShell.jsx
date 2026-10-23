import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { CreditCard, History, LayoutDashboard, LogOut, Menu, Users } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet";
import { Brand } from "@/components/common/Brand";
import { useAuth } from "@/context/AuthContext";
import { UsageMeter } from "@/components/billing/UsageMeter";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, id: "dashboard" },
  { to: "/clients", label: "Client Accounts", icon: Users, id: "clients" },
  { to: "/history", label: "History", icon: History, id: "history" },
  { to: "/billing", label: "Billing", icon: CreditCard, id: "billing" },
];

const SidebarBody = ({ onNavigate }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 h-16 flex items-center border-b border-slate-800/80">
        <Brand to="/dashboard" testId="sidebar-brand" />
      </div>
      <nav className="flex-1 px-3 py-6 space-y-1">
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            onClick={onNavigate}
            data-testid={`nav-${n.id}`}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20" : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 border border-transparent"
              }`
            }
          >
            <n.icon className="h-4 w-4" />
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-4 pb-4 space-y-4">
        {user?.page_limit && <UsageMeter user={user} compact />}
        <div className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/60 p-3">
          {user?.picture ? (
            <img src={user.picture} alt="" className="h-9 w-9 rounded-full" />
          ) : (
            <span className="h-9 w-9 rounded-full bg-slate-800 text-slate-200 text-sm font-semibold flex items-center justify-center">
              {(user?.name || user?.email || "?").charAt(0).toUpperCase()}
            </span>
          )}
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-slate-100" data-testid="sidebar-user-name">{user?.name || user?.email}</div>
            <div className="text-[11px] uppercase tracking-wider text-emerald-400" data-testid="sidebar-user-plan">{user?.plan === "free" ? "Free trial" : `${user?.plan} plan`}</div>
          </div>
          <button onClick={handleLogout} data-testid="logout-button" className="p-2 rounded-md text-slate-400 hover:text-slate-100 hover:bg-slate-800" aria-label="Log out">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export const AppShell = () => {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen bg-background">
      <aside className="hidden lg:block fixed inset-y-0 left-0 w-64 border-r border-slate-800/80 bg-[#080e21]" data-testid="app-sidebar">
        <SidebarBody />
      </aside>
      <header className="lg:hidden sticky top-0 z-30 h-14 flex items-center justify-between px-4 border-b border-slate-800 bg-[#080e21]/90 backdrop-blur-xl">
        <Brand to="/dashboard" testId="mobile-brand" />
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <button className="p-2 rounded-md text-slate-300 hover:bg-slate-800" data-testid="mobile-menu-button" aria-label="Open menu">
              <Menu className="h-5 w-5" />
            </button>
          </SheetTrigger>
          <SheetContent side="left" className="w-72 p-0 bg-[#080e21] border-slate-800">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <SidebarBody onNavigate={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
      </header>
      <main className="lg:pl-64">
        <div className="px-4 sm:px-6 lg:px-10 py-8 lg:py-10 max-w-[1400px]">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
