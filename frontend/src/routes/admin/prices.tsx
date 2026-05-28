import * as React from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { ApiError, api } from "@/lib/api-client";
import {
  PriceUnit,
  UNIT_LABEL,
  displayPrice,
  per1kToPer1m,
  per1mToPer1k,
} from "@/lib/price-format";

interface CurrentPrice {
  input_per_1k: string;
  output_per_1k: string;
  cached_input_per_1k: string | null;
  effective_from: string;
}
interface CatalogPriceRow {
  provider: string;
  model: string;
  slug: string;
  display_name: string;
  priced: boolean;
  current: CurrentPrice | null;
  in_catalog: boolean;
}
interface PriceVersion {
  id: string;
  input_per_1k: string;
  output_per_1k: string;
  cached_input_per_1k: string | null;
  effective_from: string;
  source_note: string | null;
  created_at: string;
  created_by: string;
  is_current: boolean;
}

type Unit = PriceUnit;

// 常見供應商價格範本（USD / 1M tokens，**僅為預設，請核對供應商最新公告**）
const TEMPLATES: { label: string; provider: string; model: string; in1m: string; out1m: string }[] = [
  { label: "Azure / OpenAI — gpt-4o", provider: "azure", model: "gpt-4o", in1m: "2.50", out1m: "10.00" },
  { label: "Azure / OpenAI — gpt-4o-mini", provider: "azure", model: "gpt-4o-mini", in1m: "0.15", out1m: "0.60" },
  { label: "OpenAI — gpt-4o", provider: "openai", model: "gpt-4o", in1m: "2.50", out1m: "10.00" },
  { label: "Anthropic — claude-3-5-sonnet", provider: "anthropic", model: "claude-3-5-sonnet", in1m: "3.00", out1m: "15.00" },
  { label: "Anthropic — claude-3-5-haiku", provider: "anthropic", model: "claude-3-5-haiku", in1m: "0.80", out1m: "4.00" },
  { label: "Gemini — 1.5-pro", provider: "gemini", model: "gemini-1.5-pro", in1m: "1.25", out1m: "5.00" },
];

const fmtDate = (iso: string) => new Date(iso).toLocaleString("zh-TW");

/** Local "now" formatted for a <input type="datetime-local"> (YYYY-MM-DDTHH:mm). */
function localNowForInput(): string {
  const d = new Date();
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

interface DialogState {
  provider: string;
  model: string;
  lockKey: boolean; // true when opened from a catalog row
  currentIn?: string | null; // current per-1K input price, to prefill when editing
  currentOut?: string | null;
  currentCached?: string | null; // current per-1K cached-input price
}

export function AdminPricesPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [dialog, setDialog] = React.useState<DialogState | null>(null);
  const [expanded, setExpanded] = React.useState<string | null>(null);
  const [displayUnit, setDisplayUnit] = React.useState<Unit>("per_1m");
  const unitLabel = UNIT_LABEL[displayUnit];

  const pricesQuery = useQuery<CatalogPriceRow[], ApiError>({
    queryKey: ["admin", "prices"],
    queryFn: () => api<CatalogPriceRow[]>("/admin/prices"),
  });

  return (
    <div className="container mx-auto py-8 max-w-4xl space-y-4">
      <div className="text-sm">
        <Link to="/admin/model" className="text-muted-foreground hover:underline">← 回 Model</Link>
      </div>
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">價目表</h1>
        <Button className="shrink-0" onClick={() => setDialog({ provider: "", model: "", lockKey: false })}>
          新增價格
        </Button>
      </div>
      <p className="text-sm text-muted-foreground max-w-2xl">
        每個模型的目前生效單價（USD / {unitLabel} tokens）。標「未定價」者用量成本會算成 0，請補上價格；
        批次匯入仍可用 <code className="text-xs">load_prices</code> CLI。
      </p>

      <div className="flex items-center justify-end gap-2">
        <span className="text-xs text-muted-foreground">顯示單位</span>
        <Select value={displayUnit} onValueChange={(v) => setDisplayUnit(v as Unit)}>
          <SelectTrigger className="h-8 w-[110px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="per_1m">每 1M</SelectItem>
            <SelectItem value="per_1k">每 1K</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-6">模型</TableHead>
                <TableHead className="text-right">輸入 / {unitLabel}</TableHead>
                <TableHead className="text-right">輸出 / {unitLabel}</TableHead>
                <TableHead className="text-right">快取輸入 / {unitLabel}</TableHead>
                <TableHead className="text-right">生效日</TableHead>
                <TableHead className="pr-6 text-right">動作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pricesQuery.isLoading && (
                <TableRow><TableCell colSpan={6} className="pl-6 text-muted-foreground">載入中…</TableCell></TableRow>
              )}
              {pricesQuery.data?.length === 0 && !pricesQuery.isLoading && (
                <TableRow><TableCell colSpan={6} className="pl-6 py-8 text-center text-muted-foreground">catalog 沒有任何模型</TableCell></TableRow>
              )}
              {pricesQuery.data?.map((row) => (
                <React.Fragment key={row.slug}>
                  <TableRow className="border-0">
                    <TableCell className="pl-6 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm">{row.slug}</span>
                        {!row.in_catalog && (
                          <Badge variant="outline" className="text-[10px]">不在 catalog</Badge>
                        )}
                      </div>
                      <button
                        className="mt-0.5 text-xs text-muted-foreground hover:text-foreground hover:underline"
                        onClick={() => setExpanded(expanded === row.slug ? null : row.slug)}
                      >
                        {expanded === row.slug ? "▾ 收合歷史" : "▸ 歷史版本"}
                      </button>
                    </TableCell>
                    {row.current ? (
                      <>
                        <TableCell className="text-right font-mono text-sm tabular-nums">${displayPrice(row.current.input_per_1k, displayUnit)}</TableCell>
                        <TableCell className="text-right font-mono text-sm tabular-nums">${displayPrice(row.current.output_per_1k, displayUnit)}</TableCell>
                        <TableCell className="text-right font-mono text-sm tabular-nums text-muted-foreground">
                          {row.current.cached_input_per_1k ? `$${displayPrice(row.current.cached_input_per_1k, displayUnit)}` : "—"}
                        </TableCell>
                        <TableCell className="text-right text-xs text-muted-foreground tabular-nums">{fmtDate(row.current.effective_from)}</TableCell>
                      </>
                    ) : (
                      <TableCell colSpan={4} className="text-right">
                        <Badge variant="outline" className="text-amber-700 border-amber-500">未定價</Badge>
                      </TableCell>
                    )}
                    <TableCell className="pr-6 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setDialog({
                          provider: row.provider,
                          model: row.model,
                          lockKey: true,
                          currentIn: row.current?.input_per_1k ?? null,
                          currentOut: row.current?.output_per_1k ?? null,
                          currentCached: row.current?.cached_input_per_1k ?? null,
                        })}
                      >{row.priced ? "編輯價格" : "設定價格"}</Button>
                    </TableCell>
                  </TableRow>
                  {expanded === row.slug && (
                    <TableRow className="border-0">
                      <TableCell colSpan={6} className="px-6 pb-3 pt-0">
                        <div className="rounded-md bg-muted/40 p-3">
                          <PriceHistory provider={row.provider} model={row.model} unit={displayUnit} />
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <AddPriceDialog
        state={dialog}
        onOpenChange={(open) => !open && setDialog(null)}
        onCreated={() => {
          queryClient.invalidateQueries({ queryKey: ["admin", "prices"] });
          queryClient.invalidateQueries({ queryKey: ["admin", "price-history"] });
          toast({ title: "價格已新增" });
          setDialog(null);
        }}
      />
    </div>
  );
}

function PriceHistory({ provider, model, unit }: { provider: string; model: string; unit: Unit }) {
  const q = useQuery<PriceVersion[], ApiError>({
    queryKey: ["admin", "price-history", provider, model],
    queryFn: () =>
      api<PriceVersion[]>(`/admin/prices/history?provider=${encodeURIComponent(provider)}&model=${encodeURIComponent(model)}`),
  });
  if (q.isLoading) return <span className="text-xs text-muted-foreground">載入中…</span>;
  if (!q.data || q.data.length === 0) return <span className="text-xs text-muted-foreground">尚無歷史版本</span>;
  const now = Date.now();
  return (
    <ul className="text-xs space-y-1">
      {q.data.map((v) => {
        const future = new Date(v.effective_from).getTime() > now;
        return (
          <li key={v.id} className="flex items-center gap-2">
            <span className="font-mono">{fmtDate(v.effective_from)}</span>
            <span className="font-mono">
              in ${displayPrice(v.input_per_1k, unit)} / out ${displayPrice(v.output_per_1k, unit)}
              {v.cached_input_per_1k != null && ` / cached ${displayPrice(v.cached_input_per_1k, unit)}`}
            </span>
            {v.is_current && <Badge variant="default" className="text-[10px]">目前生效</Badge>}
            {future && <Badge variant="outline" className="text-[10px]">排程生效</Badge>}
            {v.source_note && <span className="text-muted-foreground">— {v.source_note}</span>}
          </li>
        );
      })}
    </ul>
  );
}

function AddPriceDialog({
  state,
  onOpenChange,
  onCreated,
}: {
  state: DialogState | null;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const { toast } = useToast();
  const [provider, setProvider] = React.useState("");
  const [model, setModel] = React.useState("");
  const [unit, setUnit] = React.useState<Unit>("per_1m");
  const [input, setInput] = React.useState("");
  const [output, setOutput] = React.useState("");
  const [cached, setCached] = React.useState("");
  const [effective, setEffective] = React.useState("");
  const [note, setNote] = React.useState("");

  React.useEffect(() => {
    if (state) {
      setProvider(state.provider);
      setModel(state.model);
      setUnit("per_1m");
      // prefill current price (per-1K → per-1M) when editing an existing one
      setInput(state.currentIn ? per1kToPer1m(state.currentIn) : "");
      setOutput(state.currentOut ? per1kToPer1m(state.currentOut) : "");
      setCached(state.currentCached ? per1kToPer1m(state.currentCached) : "");
      setEffective(localNowForInput());
      setNote("");
    }
  }, [state]);

  const isEdit = !!(state?.currentIn || state?.currentOut);

  const applyTemplate = (label: string) => {
    const t = TEMPLATES.find((x) => x.label === label);
    if (!t) return;
    setProvider(t.provider);
    setModel(t.model);
    setUnit("per_1m");
    setInput(t.in1m);
    setOutput(t.out1m);
  };

  const mut = useMutation<unknown, ApiError, void>({
    mutationFn: () =>
      api("/admin/prices", {
        method: "POST",
        body: JSON.stringify({
          provider: provider.trim(),
          model: model.trim(),
          input_per_1k: unit === "per_1m" ? per1mToPer1k(input) : input.trim(),
          output_per_1k: unit === "per_1m" ? per1mToPer1k(output) : output.trim(),
          cached_input_per_1k: cached
            ? unit === "per_1m" ? per1mToPer1k(cached) : cached.trim()
            : null,
          effective_from: new Date(effective).toISOString(),
          source_note: note || null,
        }),
      }),
    onSuccess: () => onCreated(),
    onError: (e) => toast({ title: "新增失敗", description: e.message, variant: "destructive" }),
  });

  const unitLabel = unit === "per_1m" ? "1M" : "1K";

  return (
    <Dialog open={state !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "編輯價格" : "新增價格"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "改價會新增一個生效版本（append-only），先前的歷史帳不受影響。"
              : "新增一個價格版本（append-only），不影響歷史帳。"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>從常見範本帶入（可選）</Label>
            <Select onValueChange={applyTemplate}>
              <SelectTrigger className="mt-1"><SelectValue placeholder="選一個範本自動填入…" /></SelectTrigger>
              <SelectContent>
                {TEMPLATES.map((t) => (
                  <SelectItem key={t.label} value={t.label}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground mt-1">範本為預設值，請核對供應商最新價格。</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="p-provider">Provider</Label>
              <Input id="p-provider" className="mt-1" placeholder="azure / openai / anthropic / gemini"
                value={provider} onChange={(e) => setProvider(e.target.value)}
                disabled={state?.lockKey} />
            </div>
            <div>
              <Label htmlFor="p-model">Model（去 provider 前綴）</Label>
              <Input id="p-model" className="mt-1 font-mono" placeholder="gpt-5.4-mini"
                value={model} onChange={(e) => setModel(e.target.value)}
                disabled={state?.lockKey} />
            </div>
          </div>

          <div>
            <Label>單價單位</Label>
            <Select value={unit} onValueChange={(v) => setUnit(v as Unit)}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="per_1m">每 1M tokens（供應商頁面慣用）</SelectItem>
                <SelectItem value="per_1k">每 1K tokens</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="p-in">輸入單價 / {unitLabel}（USD）</Label>
              <Input id="p-in" className="mt-1 font-mono" placeholder={unit === "per_1m" ? "0.15" : "0.00015"}
                value={input} onChange={(e) => setInput(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="p-out">輸出單價 / {unitLabel}（USD）</Label>
              <Input id="p-out" className="mt-1 font-mono" placeholder={unit === "per_1m" ? "0.60" : "0.0006"}
                value={output} onChange={(e) => setOutput(e.target.value)} />
            </div>
          </div>
          <div>
            <Label htmlFor="p-cached">快取輸入單價 / {unitLabel}（USD，可選）</Label>
            <Input id="p-cached" className="mt-1 font-mono" placeholder={unit === "per_1m" ? "0.0375（留空＝不打折）" : "0.0000375"}
              value={cached} onChange={(e) => setCached(e.target.value)} />
            <p className="text-xs text-muted-foreground mt-1">
              命中提示快取的輸入 token 套此折扣價；留空則以一般輸入價計。
            </p>
          </div>
          {unit === "per_1m" && (input || output || cached) && (
            <p className="text-xs text-muted-foreground">
              換算後（每 1K）：in ${input ? per1mToPer1k(input) : "—"} / out ${output ? per1mToPer1k(output) : "—"}
              {cached && ` / cached $${per1mToPer1k(cached)}`}
            </p>
          )}

          <div>
            <Label htmlFor="p-eff">生效時間</Label>
            <Input id="p-eff" type="datetime-local" className="mt-1" value={effective} onChange={(e) => setEffective(e.target.value)} />
            <p className="text-xs text-muted-foreground mt-1">預設為「現在」，可立即生效；同一模型不同時間可各有版本。</p>
          </div>
          <div>
            <Label htmlFor="p-note">來源備註（可選）</Label>
            <Input id="p-note" className="mt-1" placeholder="Azure pricing page 2026-05" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button
            disabled={!provider.trim() || !model.trim() || !input || !output || !effective || mut.isPending}
            onClick={() => mut.mutate()}
          >{isEdit ? "儲存" : "新增"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
