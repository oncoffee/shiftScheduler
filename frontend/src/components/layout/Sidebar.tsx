import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  Store,
  Calendar,
  History,
  FileText,
  Settings,
} from "lucide-react";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/employees", icon: Users, label: "Employees" },
  { to: "/stores", icon: Store, label: "Stores" },
  { to: "/schedule", icon: Calendar, label: "Schedule" },
  { to: "/history", icon: History, label: "History" },
  { to: "/logs", icon: FileText, label: "Logs" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  return (
    <aside className="w-64 border-r bg-card h-screen sticky top-0">
      <div className="p-6">
        <h1 className="text-xl font-bold">Shift Scheduler</h1>
      </div>
      <nav className="px-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
