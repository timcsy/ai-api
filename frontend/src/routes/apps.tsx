import { Link } from "react-router-dom";

import { Card, CardContent } from "@/components/ui/card";
import { APPLICATIONS } from "@/lib/applications";

/**
 * Phase 28: 應用商店 — a grid of application tiles (logo + name + blurb).
 * Click a tile → /apps/:id detail page (install + create-key for that app).
 */
export function ApplicationsPage() {
  return (
    <div className="container mx-auto py-8 space-y-6">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">應用</h1>
        <p className="text-muted-foreground mt-2">
          把分配到的金鑰接上你慣用的工具。點一個應用看怎麼接。
        </p>
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {APPLICATIONS.map((app) => (
          <Link key={app.id} to={`/apps/${app.id}`} className="block" aria-label={app.name}>
            <Card className="h-full transition-colors hover:bg-accent">
              <CardContent className="flex items-start gap-3 p-4">
                <div className="shrink-0 rounded-md bg-muted p-2 text-foreground">
                  <app.Logo className="h-8 w-8" />
                </div>
                <div className="min-w-0">
                  <div className="font-semibold">{app.name}</div>
                  <p className="text-sm text-muted-foreground">{app.blurb}</p>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </section>
    </div>
  );
}
