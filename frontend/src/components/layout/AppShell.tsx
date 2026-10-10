import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  Bell,
  Boxes,
  Gauge,
  LineChart as LineChartIcon,
  LogOut,
  Map,
  Menu,
  Moon,
  Settings,
  Sparkles,
  Sun,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { Button } from "@/components/ui/button";
import { ChatbotWidget } from "@/components/chat/ChatbotWidget";
import { canAccess, routeRoles } from "@/lib/roles";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Executive", icon: Gauge, end: true, roles: routeRoles.executive },
  { to: "/forecast", label: "Forecasting", icon: LineChartIcon, roles: routeRoles.operations },
  { to: "/inventory", label: "Inventory", icon: Boxes, roles: routeRoles.operations },
  { to: "/analytics", label: "Analytics", icon: Map, roles: routeRoles.analytics },
  { to: "/anomalies", label: "Anomalies", icon: Bell, roles: routeRoles.anomalies },
  { to: "/recommendations", label: "AI Actions", icon: Sparkles, roles: routeRoles.operations },
  { to: "/reports", label: "Reports", icon: Activity, roles: routeRoles.reports },
  { to: "/settings", label: "Settings", icon: Settings, roles: routeRoles.settings },
] as const;

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  return (
    <>
      {nav
        .filter((item) => canAccess(user?.role, item.roles))
        .map((item) => {
          const { to, label, icon: Icon } = item;
          const end = "end" in item ? item.end : false;
          return (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "group relative flex items-center gap-3 rounded-[var(--radius)] px-3 py-2.5 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-[var(--accent)]/12 text-[var(--text)]"
                    : "text-[var(--muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]",
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive ? (
                    <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-full bg-[var(--accent)]" />
                  ) : null}
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0 transition-colors",
                      isActive ? "text-[var(--accent)]" : "text-[var(--muted)] group-hover:text-[var(--text)]",
                    )}
                  />
                  {label}
                </>
              )}
            </NavLink>
          );
        })}
    </>
  );
}

export function AppShell() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const roleLabel = user?.role?.replace(/_/g, " ") ?? "";

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside
        className="glass-panel-strong fixed inset-y-0 left-0 z-40 hidden w-[var(--sidebar-width)] flex-col border-r border-[var(--border)] md:flex"
        aria-label="Main navigation"
      >
        <div className="flex h-16 items-center gap-3 border-b border-[var(--border)] px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--violet)] text-[var(--accent-foreground)] shadow-[var(--shadow-glow)]">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[var(--muted)]">
              Stocker
            </p>
            <p className="text-sm font-semibold text-[var(--text)]">Enterprise AI</p>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-3">
          <NavItems />
        </nav>
        <div className="border-t border-[var(--border)] p-4">
          <div className="rounded-[var(--radius)] bg-[var(--surface2)] p-3">
            <p className="truncate text-sm font-medium text-[var(--text)]">{user?.email}</p>
            <p className="truncate text-xs capitalize text-[var(--muted)]">{roleLabel}</p>
          </div>
          <div className="mt-2 flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              type="button"
              onClick={toggleTheme}
              aria-label="Toggle theme"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="flex-1 justify-start text-[var(--muted)]"
              type="button"
              onClick={() => void logout()}
            >
              <LogOut className="mr-2 h-4 w-4" /> Sign out
            </Button>
          </div>
        </div>
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen ? (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm md:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 320 }}
              className="glass-panel-strong fixed inset-y-0 left-0 z-50 flex w-[min(85vw,280px)] flex-col border-r border-[var(--border)] md:hidden"
            >
              <div className="flex h-14 items-center justify-between border-b border-[var(--border)] px-4">
                <span className="font-semibold">Stocker</span>
                <Button variant="ghost" size="icon" type="button" onClick={() => setMobileOpen(false)}>
                  <X className="h-5 w-5" />
                </Button>
              </div>
              <nav className="flex flex-1 flex-col gap-0.5 p-3">
                <NavItems onNavigate={() => setMobileOpen(false)} />
              </nav>
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>

      <div className="flex min-h-screen flex-1 flex-col md:pl-[var(--sidebar-width)]">
        <header className="glass-panel sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-[var(--border)] px-4 md:px-8">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </Button>
            <span className="text-sm font-medium text-[var(--muted)] md:hidden">
              {nav.find((n) => location.pathname === n.to || (n.to !== "/" && location.pathname.startsWith(n.to)))?.label ?? "Stocker"}
            </span>
          </div>
          <div className="flex items-center gap-2 md:hidden">
            <Button variant="ghost" size="icon" type="button" onClick={toggleTheme}>
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button variant="outline" size="sm" type="button" onClick={() => void logout()}>
              Out
            </Button>
          </div>
        </header>

        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="flex-1 overflow-auto px-4 py-6 md:px-8 md:py-8"
        >
          <Outlet />
        </motion.main>
      </div>

      {/* Floating Stocker AI Copilot Assistant */}
      <ChatbotWidget />
    </div>
  );
}
