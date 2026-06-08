import { Github, Menu } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";

const GITHUB_URL = "https://github.com/timcsy/ai-api";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "text-sm font-medium transition-colors hover:text-foreground",
    isActive ? "text-foreground" : "text-muted-foreground",
  );

const subNavClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    // Phase 16: shrink-0 + whitespace-nowrap so the horizontal sub-nav scrolls
    // instead of squeezing Chinese labels into one-character-per-line columns.
    "shrink-0 whitespace-nowrap text-sm transition-colors hover:text-foreground",
    isActive ? "text-foreground font-semibold" : "text-muted-foreground",
  );

// Phase 5.1: consolidated 6 entries (was 11)
const ADMIN_SUBNAV = [
  { to: "/admin", label: "首頁", end: true },
  { to: "/admin/model", label: "模型" },
  { to: "/admin/member", label: "成員" },
  { to: "/admin/tag", label: "標籤" },
  { to: "/admin/providers", label: "供應商憑證" },
  { to: "/admin/access", label: "存取" },
  { to: "/admin/notifications", label: "通知" },
  { to: "/admin/observability", label: "觀測" },
];

const MAIN_NAV = [
  { to: "/dashboard", label: "我的儀表板", adminOnly: false },
  { to: "/keys", label: "金鑰", adminOnly: false },
  { to: "/allocations", label: "分配", adminOnly: false },
  { to: "/usage", label: "用量", adminOnly: false },
  { to: "/catalog", label: "模型目錄", adminOnly: false },
  { to: "/admin", label: "管理員", adminOnly: true },
];

export function AppShell() {
  const { member, logout } = useAuth();
  const isMobile = useIsMobile();
  const isAdmin = member?.is_admin === true;

  return (
    <div className="min-h-screen flex flex-col bg-muted/30">
      <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        {isMobile ? (
          <MobileHeader isAdmin={isAdmin} email={member?.email} onLogout={() => void logout()} />
        ) : (
          <DesktopHeader isAdmin={isAdmin} email={member?.email} onLogout={() => void logout()} />
        )}
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}

function DesktopHeader({
  isAdmin,
  email,
  onLogout,
}: {
  isAdmin: boolean;
  email: string | undefined;
  onLogout: () => void;
}) {
  // Only surface the admin sub-nav while actually inside the admin area —
  // it shouldn't clutter a member-facing page just because you're an admin.
  const onAdminRoute = useLocation().pathname.startsWith("/admin");
  return (
    <>
      <div className="container mx-auto flex h-14 items-center">
        <div className="mr-6 flex items-center space-x-2">
          <span className="font-bold">AI API Manager</span>
        </div>
        <nav className="flex items-center space-x-6">
          {MAIN_NAV.filter((n) => !n.adminOnly || isAdmin).map((n) => (
            <NavLink key={n.to} to={n.to} className={navLinkClass} end={n.to === "/admin"}>
              {n.label}
            </NavLink>
          ))}
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
            {email}
          </span>
          <Separator orientation="vertical" className="h-6" />
          <Button variant="outline" size="sm" onClick={onLogout}>
            登出
          </Button>
        </div>
      </div>
      {isAdmin && onAdminRoute && (
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
    </>
  );
}

function MobileHeader({
  isAdmin,
  email,
  onLogout,
}: {
  isAdmin: boolean;
  email: string | undefined;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  const mainItems = MAIN_NAV.filter((n) => !n.adminOnly || isAdmin);

  return (
    <div className="container mx-auto flex h-14 items-center justify-between">
      <span className="font-bold">AI API Manager</span>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="開啟選單">
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="right" className="w-72">
          <SheetTitle>選單</SheetTitle>
          <nav className="flex flex-col gap-1">
            {mainItems.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/admin"}
                onClick={close}
                className="rounded-md px-2 py-2 text-sm font-medium hover:bg-muted"
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          {isAdmin && (
            <div className="border-t pt-3">
              <div className="px-2 pb-1 text-xs text-muted-foreground">管理區</div>
              <nav className="flex flex-col gap-1">
                {ADMIN_SUBNAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={close}
                    className="rounded-md px-2 py-2 text-sm hover:bg-muted"
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>
          )}
          <div className="mt-auto border-t pt-3 space-y-3">
            <div className="truncate px-2 text-sm text-muted-foreground" data-testid="member-email">
              {email}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => {
                close();
                onLogout();
              }}
            >
              登出
            </Button>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-2 text-sm text-muted-foreground hover:text-foreground"
            >
              <Github className="h-5 w-5" />
              <span>給個星星 ⭐</span>
            </a>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
