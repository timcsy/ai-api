import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";

const TABS = [
  { to: "usage", label: "用量" },
  { to: "allocations", label: "分配" },
  { to: "quota", label: "配額池" },
  { to: "rebalance", label: "重新平衡記錄" },
  { to: "audit", label: "稽核紀錄" },
];

const tabClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    // Phase 16 (RWD): shrink-0 + whitespace-nowrap so this horizontal tab row
    // scrolls on phones instead of squeezing labels into vertical char columns.
    "shrink-0 whitespace-nowrap px-3 py-2 text-sm font-medium border-b-2 transition-colors",
    isActive
      ? "border-primary text-foreground"
      : "border-transparent text-muted-foreground hover:text-foreground",
  );

export function AdminObservabilityPage() {
  return (
    <div>
      <div className="border-b bg-muted/30">
        <div className="container mx-auto flex items-center gap-2 overflow-x-auto">
          {TABS.map((t) => (
            <NavLink key={t.to} to={t.to} className={tabClass}>
              {t.label}
            </NavLink>
          ))}
        </div>
      </div>
      <Outlet />
    </div>
  );
}
