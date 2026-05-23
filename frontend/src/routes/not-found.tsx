import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
      <h1 className="text-4xl font-bold">404</h1>
      <p className="text-muted-foreground">找不到頁面</p>
      <Button asChild variant="outline">
        <Link to="/">回首頁</Link>
      </Button>
    </div>
  );
}
