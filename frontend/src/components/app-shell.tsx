import { Github } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/contexts/auth";
import { cn } from "@/lib/utils";

const GITHUB_URL = "https://github.com/timcsy/ai-api";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "text-sm font-medium transition-colors hover:text-foreground",
    isActive ? "text-foreground" : "text-muted-foreground",
  );

const subNavClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "text-sm transition-colors hover:text-foreground",
    isActive ? "text-foreground font-semibold" : "text-muted-foreground",
  );

// Phase 5.1: consolidated 6 entries (was 11)
const ADMIN_SUBNAV = [
  { to: "/admin", label: "首頁", end: true },
  { to: "/admin/model", label: "Model" },
  { to: "/admin/member", label: "成員" },
  { to: "/admin/tag", label: "Tag" },
  { to: "/admin/providers", label: "Provider 憑證" },
  { to: "/admin/access", label: "存取" },
  { to: "/admin/observability", label: "觀測" },
];

export function AppShell() {
  const { member, logout } = useAuth();
  const location = useLocation();
  // Show admin sub-nav whenever the current user is admin, not only inside
  // /admin/* — admins jumping in from /dashboard or /catalog still need quick
  // access to admin pages.
  void location;
  return (
    <div className="min-h-screen flex flex-col bg-muted/30">
      <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-14 items-center">
          <div className="mr-6 flex items-center space-x-2">
            <span className="font-bold">AI API Manager</span>
          </div>
          <nav className="flex items-center space-x-6">
            <NavLink to="/dashboard" className={navLinkClass}>
              我的儀表板
            </NavLink>
            <NavLink to="/catalog" className={navLinkClass}>
              模型目錄
            </NavLink>
            {member?.is_admin === true && (
              <NavLink to="/admin" className={navLinkClass}>
                管理員
              </NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center space-x-3">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              aria-label="在 GitHub 給個星星 ⭐"
              title="喜歡的話到 GitHub 給個星星 ⭐"
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <Github className="h-5 w-5" />
              <span className="hidden sm:inline">Star</span>
            </a>
            <Separator orientation="vertical" className="h-6" />
            <span className="text-sm text-muted-foreground" data-testid="member-email">
              {member?.email}
            </span>
            <Separator orientation="vertical" className="h-6" />
            <Button variant="outline" size="sm" onClick={() => void logout()}>
              登出
            </Button>
          </div>
        </div>
        {member?.is_admin === true && (
          <div className="border-t bg-background/60">
            <div className="container mx-auto flex h-10 items-center gap-5 overflow-x-auto">
              {ADMIN_SUBNAV.map((item) => (
                <NavLink key={item.to} to={item.to} className={subNavClass} end={item.end}>
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        )}
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
