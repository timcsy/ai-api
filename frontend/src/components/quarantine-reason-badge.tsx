import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ApiError, api } from "@/lib/api-client";

interface QuarantineReason {
  allocation_id: string;
  event_type: string | null;
  reason: string | null;
  last_hour_calls: number | null;
  baseline_per_hour: number | null;
  occurred_at: string | null;
  message: string;
}

/**
 * Phase 14 (US4): the quarantined/paused status badge, clickable to reveal WHY
 * the allocation was auto-stopped. The reason is fetched lazily on first open so
 * the allocations table doesn't fire one request per row up front.
 */
export function QuarantineReasonBadge({
  allocationId,
  status,
}: {
  allocationId: string;
  status: "quarantined" | "paused";
}) {
  const [open, setOpen] = useState(false);
  const q = useQuery<QuarantineReason, ApiError>({
    queryKey: ["admin", "quarantine-reason", allocationId],
    enabled: open,
    queryFn: () =>
      api<QuarantineReason>(`/admin/allocations/${allocationId}/quarantine-reason`),
  });

  const label = status === "quarantined" ? "🚨 已隔離" : "已暫停";
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Badge
          variant={status === "quarantined" ? "destructive" : "outline"}
          className={`cursor-pointer ${status === "paused" ? "text-amber-700 border-amber-500" : ""}`}
          title="點擊看觸發原因"
        >
          {label} ⓘ
        </Badge>
      </PopoverTrigger>
      <PopoverContent className="w-72 text-sm">
        <div className="font-medium mb-1">
          {status === "quarantined" ? "自動隔離原因" : "暫停原因"}
        </div>
        {q.isLoading && <p className="text-muted-foreground">載入中…</p>}
        {q.error && <p className="text-destructive">無法載入原因</p>}
        {q.data && (
          <>
            <p className="text-muted-foreground">{q.data.message}</p>
            {q.data.occurred_at && (
              <p className="mt-1 text-xs text-muted-foreground">
                發生於 {new Date(q.data.occurred_at).toLocaleString("zh-TW")}
              </p>
            )}
            {status === "quarantined" && (
              <p className="mt-2 text-xs text-muted-foreground">
                確認無誤可在右側操作選單「解除隔離」；若為已知服務／agent 用途，可標為「服務型」永久豁免。
              </p>
            )}
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
