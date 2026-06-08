import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";

interface Diff {
  field: string;
  current: unknown;
  latest: unknown;
  source: "litellm" | "borrowed" | "manual";
  changed: boolean;
}
interface CheckResult {
  source: "live" | "bundled-fallback";
  litellm_version: string;
  base_model_key: string;
  diffs: Diff[];
}

const show = (v: unknown) => (Array.isArray(v) ? v.join(", ") : v === null || v === undefined ? "—" : String(v));

/**
 * Phase 23: "check LiteLLM updates" for one catalog model. Fetches the latest
 * registry (live, with bundled fallback), shows per-field old→new diffs with
 * provenance, and applies only the fields the admin selects. Manual fields are
 * never auto-overwritten.
 */
export function LiteLLMUpdateDiff({
  slug,
  open,
  onOpenChange,
  onApplied,
}: {
  slug: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onApplied?: () => void;
}) {
  const { toast } = useToast();
  const [result, setResult] = React.useState<CheckResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [picked, setPicked] = React.useState<Set<string>>(new Set());
  const [applying, setApplying] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    setResult(null);
    setPicked(new Set());
    setLoading(true);
    api<CheckResult>(`/admin/catalog/models/${slug}/litellm-check`, { method: "POST" })
      .then((r) => setResult(r))
      .catch((e: ApiError) => toast({ title: "檢查失敗", description: e.message, variant: "destructive" }))
      .finally(() => setLoading(false));
  }, [open, slug, toast]);

  const changed = (result?.diffs ?? []).filter((d) => d.changed);

  async function apply() {
    setApplying(true);
    try {
      await api(`/admin/catalog/models/${slug}/litellm-apply`, {
        method: "POST",
        body: JSON.stringify({ fields: [...picked], litellm_version: result?.litellm_version }),
      });
      toast({ title: "已套用更新" });
      onOpenChange(false);
      onApplied?.();
    } catch (e) {
      toast({ title: "套用失敗", description: (e as ApiError).message, variant: "destructive" });
    } finally {
      setApplying(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>檢查 LiteLLM 更新：{slug}</DialogTitle>
          <DialogDescription>
            勾選要採納的欄位。手動改過的欄位不會被覆寫；採納價格會新增一筆價目版本（不蓋舊的）。
          </DialogDescription>
        </DialogHeader>
        {loading && <p className="text-sm text-muted-foreground">讀取最新登錄表…</p>}
        {result && (
          <>
            <p className="text-xs text-muted-foreground">
              來源：{result.source === "live" ? "線上最新" : "離線固定版（線上抓取失敗，已回退）"}
              · litellm {result.litellm_version} · 對照 {result.base_model_key}
            </p>
            {changed.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">沒有可更新的差異。</p>
            ) : (
              <ul className="max-h-80 space-y-2 overflow-y-auto">
                {changed.map((d) => {
                  const manual = d.source === "manual";
                  return (
                    <li key={d.field} className="flex items-start gap-2 rounded border p-2 text-sm">
                      <Checkbox
                        className="mt-0.5"
                        disabled={manual}
                        checked={picked.has(d.field)}
                        onCheckedChange={(v) =>
                          setPicked((s) => {
                            const n = new Set(s);
                            if (v) n.add(d.field); else n.delete(d.field);
                            return n;
                          })
                        }
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs">{d.field}</span>
                          <Badge variant={manual ? "outline" : "secondary"} className="text-[10px]">
                            {manual ? "手動（不會覆寫）" : d.source === "borrowed" ? "借用" : "LiteLLM"}
                          </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground break-words">
                          {show(d.current)} <span className="mx-1">→</span>
                          <span className="text-foreground">{show(d.latest)}</span>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>關閉</Button>
          <Button disabled={picked.size === 0 || applying} onClick={() => void apply()}>
            {applying ? "套用中…" : `採納 ${picked.size} 項`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
