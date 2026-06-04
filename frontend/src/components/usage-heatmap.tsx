export interface HeatCell {
  weekday: number; // 0=Sunday .. 6=Saturday
  hour: number; // 0..23
  tokens: number;
  call_count: number;
}

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];
const fmtInt = new Intl.NumberFormat("zh-TW");

/**
 * Weekday × hour usage heatmap body — a plain CSS grid of ≤168 coloured cells
 * (far cheaper than recharts for this). Shared by the admin usage page and the
 * per-allocation member view; the caller wraps it in its own Card.
 */
export function UsageHeatmap({
  cells,
  isLoading,
  height = 200,
}: {
  cells: HeatCell[];
  isLoading?: boolean;
  height?: number;
}) {
  if (isLoading) {
    return <div className="animate-pulse rounded-md bg-muted/50" style={{ height }} />;
  }
  if (cells.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground"
        style={{ height }}
      >
        此區間沒有資料
      </div>
    );
  }

  const cellMap = new Map(cells.map((c) => [`${c.weekday}-${c.hour}`, c]));
  const maxTokens = cells.reduce((m, c) => Math.max(m, c.tokens), 0);

  return (
    <div className="overflow-x-auto">
      {/* 1fr hour columns fill the card width on desktop; min-w keeps it usable
          + scrollable on phones (Phase 16 RWD). */}
      <div
        className="grid w-full min-w-[560px] gap-[3px]"
        style={{ gridTemplateColumns: "auto repeat(24, minmax(0, 1fr))" }}
      >
        <div />
        {Array.from({ length: 24 }, (_, h) => (
          <div key={`h-${h}`} className="text-[9px] text-muted-foreground text-center">
            {h % 3 === 0 ? h : ""}
          </div>
        ))}
        {WEEKDAYS.map((label, wd) => (
          <Row key={wd} label={label} wd={wd} cellMap={cellMap} maxTokens={maxTokens} />
        ))}
      </div>
      <p className="mt-2 text-[10px] text-muted-foreground">列＝星期（日～六），欄＝0–23 時</p>
    </div>
  );
}

function Row({
  label,
  wd,
  cellMap,
  maxTokens,
}: {
  label: string;
  wd: number;
  cellMap: Map<string, HeatCell>;
  maxTokens: number;
}) {
  return (
    <>
      <div className="flex items-center pr-2 text-[11px] text-muted-foreground">週{label}</div>
      {Array.from({ length: 24 }, (_, h) => {
        const c = cellMap.get(`${wd}-${h}`);
        const intensity = c && maxTokens > 0 ? 0.12 + 0.88 * (c.tokens / maxTokens) : 0;
        return (
          <div
            key={h}
            className="h-6 w-full rounded-[3px] border border-border/30"
            style={{ backgroundColor: c ? `rgba(37, 99, 235, ${intensity})` : "transparent" }}
            title={
              c
                ? `週${label} ${h}:00 — ${fmtInt.format(c.tokens)} tokens · ${c.call_count} 次`
                : `週${label} ${h}:00 — 無`
            }
          />
        );
      })}
    </>
  );
}
