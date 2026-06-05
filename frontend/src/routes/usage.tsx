import * as React from "react";

import { MemberUsageCharts } from "@/components/member-usage-charts";
import { TimeRangeSelect } from "@/components/time-range-select";
import { UsageSummary } from "@/components/usage-summary";
import { presetRange } from "@/lib/time-range";

export function UsagePage() {
  // Phase 17: one time range drives both of the member's own usage charts.
  const [usageRange, setUsageRange] = React.useState(() => presetRange("month"));
  return (
    <div className="container mx-auto py-8 space-y-6">
      <section>
        <h1 className="text-3xl font-bold tracking-tight">用量</h1>
      </section>
      <section className="space-y-4">
        <UsageSummary />
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h2 className="text-lg font-semibold">用量圖表</h2>
          <TimeRangeSelect value={usageRange} onChange={setUsageRange} />
        </div>
        <MemberUsageCharts range={usageRange} />
      </section>
    </div>
  );
}
