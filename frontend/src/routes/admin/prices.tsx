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

const fmtDate = (iso: string) => new Date(iso).toLocaleString("zh-TW");

// Phase 31: non-token billing unit labels.
const UNIT_ZH: Record<string, string> = {
  page: "頁", query: "查詢", character: "字元", image: "張", second: "秒", minute: "分鐘",
};

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
        <Link to="/admin/model" className="text-muted-foreground hover:underline">← 回模型</Link>
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
          <Table className="responsive-table">
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
                <TableRow><TableCell colSpan={6} className="pl-6 py-8 text-center text-muted-foreground">目錄沒有任何模型</TableCell></TableRow>
              )}
              {pricesQuery.data?.map((row) => (
                <React.Fragment key={row.slug}>
                  <TableRow className="border-0">
                    <TableCell className="pl-6 py-3" data-label="模型">
                      <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm break-all">{row.slug}</span>
                        {!row.in_catalog && (
                          <Badge variant="outline" className="text-[10px]">不在目錄</Badge>
                        )}
                      </div>
                      <button
                        className="mt-0.5 text-xs text-muted-foreground hover:text-foreground hover:underline"
                        onClick={() => setExpanded(expanded === row.slug ? null : row.slug)}
                      >
                        {expanded === row.slug ? "▾ 收合歷史" : "▸ 歷史版本"}
                      </button>
                      </div>
                    </TableCell>
                    {row.current ? (
                      <>
                        <TableCell className="text-right font-mono text-sm tabular-nums" data-label="輸入">${displayPrice(row.current.input_per_1k, displayUnit)}</TableCell>
                        <TableCell className="text-right font-mono text-sm tabular-nums" data-label="輸出">${displayPrice(row.current.output_per_1k, displayUnit)}</TableCell>
                        <TableCell className="text-right font-mono text-sm tabular-nums text-muted-foreground" data-label="快取輸入">
                          {row.current.cached_input_per_1k ? `$${displayPrice(row.current.cached_input_per_1k, displayUnit)}` : "—"}
                        </TableCell>
                        <TableCell className="text-right text-xs text-muted-foreground tabular-nums" data-label="生效日">{fmtDate(row.current.effective_from)}</TableCell>
                      </>
                    ) : (
                      <TableCell colSpan={4} className="text-right" data-label="價格">
                        <Badge variant="outline" className="text-amber-700 border-amber-500">未定價</Badge>
                      </TableCell>
                    )}
                    <TableCell className="pr-6 text-right" data-label="動作">
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
  const [perPage, setPerPage] = React.useState("");  // Phase 29 ②: non-token unit price value
  const [perUnit, setPerUnit] = React.useState("page");  // Phase 31: the unit (page/query/character/image/second)
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
      setPerPage("");
      setPerUnit("page");
      setEffective(localNowForInput());
      setNote("");
    }
  }, [state]);

  const isEdit = !!(state?.currentIn || state?.currentOut);

  const [litellmBusy, setLitellmBusy] = React.useState(false);
  // Phase 24: bring in the suggested price from LiteLLM (replaces the old hardcoded
  // templates) using the current provider + model as the registry key.
  const bringInLitellm = async () => {
    const p = provider.trim();
    const m = model.trim();
    if (!p || !m) {
      toast({ title: "請先填供應商與模型" });
      return;
    }
    setLitellmBusy(true);
    try {
      const s = await api<{
        suggested_price: {
          input_per_1k: string; output_per_1k: string; cached_input_per_1k: string | null;
          price_unit?: string | null; price_per_unit?: string | null;
        } | null;
      }>(`/admin/catalog/litellm/suggest/${p}/${m}`);
      if (!s.suggested_price) {
        toast({ title: "LiteLLM 無此模型的建議價，請手填" });
        return;
      }
      // Phase 31: non-token suggestion (OCR per-page, rerank per-query, …)
      if (s.suggested_price.price_unit && s.suggested_price.price_per_unit) {
        setPerUnit(s.suggested_price.price_unit);
        setPerPage(s.suggested_price.price_per_unit);
        toast({ title: `已帶入每${UNIT_ZH[s.suggested_price.price_unit] ?? s.suggested_price.price_unit}建議價` });
        return;
      }
      setUnit("per_1m");
      setInput(per1kToPer1m(s.suggested_price.input_per_1k));
      setOutput(per1kToPer1m(s.suggested_price.output_per_1k));
      if (s.suggested_price.cached_input_per_1k) setCached(per1kToPer1m(s.suggested_price.cached_input_per_1k));
    } catch {
      toast({ title: "LiteLLM 無此模型的建議價，請手填" });
    } finally {
      setLitellmBusy(false);
    }
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
          price_unit: perPage.trim() ? perUnit : null,
          price_per_unit: perPage.trim() || null,
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
      <DialogContent className="max-h-[85vh] overflow-y-auto">
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
            <Button type="button" variant="outline" size="sm" onClick={() => void bringInLitellm()} disabled={litellmBusy}>
              {litellmBusy ? "查詢中…" : "從 LiteLLM 帶入建議價"}
            </Button>
            <p className="text-xs text-muted-foreground mt-1">
              依供應商 + 模型 取 LiteLLM 公開牌價填入（可再手改）；查無則請手填。
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label htmlFor="p-provider">供應商</Label>
              <Input id="p-provider" className="mt-1" placeholder="azure / openai / anthropic / gemini"
                value={provider} onChange={(e) => setProvider(e.target.value)}
                disabled={state?.lockKey} />
            </div>
            <div>
              <Label htmlFor="p-model">模型（去供應商前綴）</Label>
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

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
            <Label htmlFor="p-perpage">每{UNIT_ZH[perUnit] ?? perUnit}價（USD，非 token 模型；可選）</Label>
            <div className="flex gap-2 mt-1">
              <Select value={perUnit} onValueChange={setPerUnit}>
                <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="page">每頁</SelectItem>
                  <SelectItem value="query">每查詢</SelectItem>
                  <SelectItem value="character">每字元</SelectItem>
                  <SelectItem value="image">每張</SelectItem>
                  <SelectItem value="second">每秒</SelectItem>
                  <SelectItem value="minute">每分鐘</SelectItem>
                </SelectContent>
              </Select>
              <Input id="p-perpage" className="font-mono flex-1" placeholder="0.003"
                value={perPage} onChange={(e) => setPerPage(e.target.value)} />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              非 token 模型（OCR=頁、rerank/search=查詢、TTS=字元、圖片編輯=張、即時字幕=分鐘）依該單位計費，填此欄；token 欄可填 0。一筆價格只用一種單位。可按上方「從 LiteLLM 帶入建議價」自動填。
            </p>
          </div>

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
