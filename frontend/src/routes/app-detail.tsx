import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { getApplication } from "@/lib/applications";

/** Phase 28: a single application's home (storefront detail). */
export function AppDetailPage() {
  const { appId } = useParams();
  const app = getApplication(appId);

  if (!app) {
    return (
      <div className="container mx-auto py-10 max-w-md text-center space-y-4">
        <h1 className="text-xl font-semibold">找不到這個應用</h1>
        <Button asChild variant="outline">
          <Link to="/apps">回應用</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-3xl space-y-6">
      <Link to="/apps" className="text-sm text-muted-foreground hover:underline">← 應用</Link>
      <section className="flex items-start gap-4">
        <div className="shrink-0 rounded-md bg-muted p-3 text-foreground">
          <app.Logo className="h-10 w-10" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{app.name}</h1>
          <p className="text-muted-foreground mt-1">{app.blurb}</p>
        </div>
      </section>
      <app.Detail />
    </div>
  );
}
