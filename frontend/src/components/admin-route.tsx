import { Link, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/auth";

export function AdminRoute() {
  const { status, member } = useAuth();

  if (status === "loading") {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="text-muted-foreground">載入中…</div>
      </div>
    );
  }

  if (member?.is_admin !== true) {
    return (
      <div className="container mx-auto py-16 max-w-md text-center space-y-4">
        <h1 className="text-2xl font-semibold">無權限查看</h1>
        <p className="text-muted-foreground">此頁面僅供管理員存取。</p>
        <Button asChild variant="outline">
          <Link to="/dashboard">回首頁</Link>
        </Button>
      </div>
    );
  }

  return <Outlet />;
}
