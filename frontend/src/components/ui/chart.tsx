import * as React from "react";
import { ResponsiveContainer } from "recharts";

import { cn } from "@/lib/utils";

/**
 * Shared chart wrapper (Phase 14). Wraps recharts in a fixed-height responsive
 * container with a consistent empty state, so every chart on the platform looks
 * and behaves the same (one chart lib, one wrapper — avoids per-chart drift).
 */
export function Chart({
  isEmpty,
  isLoading,
  emptyText = "此區間沒有資料",
  height = 240,
  className,
  children,
}: {
  isEmpty?: boolean;
  isLoading?: boolean;
  emptyText?: string;
  height?: number;
  className?: string;
  children: React.ReactElement;
}) {
  // Loading takes precedence over empty so switching the time range shows a
  // skeleton instead of a misleading "no data" flash (Phase 14 US3).
  if (isLoading) {
    return (
      <div
        data-testid="chart"
        className={cn("animate-pulse rounded-md bg-muted/50", className)}
        style={{ height }}
      />
    );
  }
  if (isEmpty) {
    return (
      <div
        data-testid="chart"
        className={cn(
          "flex items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground",
          className,
        )}
        style={{ height }}
      >
        {emptyText}
      </div>
    );
  }
  return (
    // w-full + min-w-0 so recharts' ResponsiveContainer can shrink inside grid/
    // flex parents instead of overflowing the viewport on phones (Phase 16 fix).
    <div data-testid="chart" className={cn("w-full min-w-0", className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}
