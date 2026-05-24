import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
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
import { apiBlob, triggerDownload } from "@/lib/download";

interface UsageItem {
  group_key: string;
  display_name: string | null;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_cost_usd: number;
  call_count: number;
}

interface UsageResponse {
  from: string;
  to: string;
  group_by: string;
  items: UsageItem[];
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function thirtyDaysAgo(): string {
  const d = new Date();
  d.setDate(d.getDate() - 30);
  return isoDate(d);
}

export function AdminUsagePage() {
  const [params, setParams] = useSearchParams();
  const { toast } = useToast();

  const from = params.get("from") ?? thirtyDaysAgo();
  const to = params.get("to") ?? isoDate(new Date());
  const groupBy = (params.get("group_by") ?? "member") as "member" | "allocation" | "model";
  const serviceOnly = params.get("service_only") === "true";

  const fromIso = `${from}T00:00:00Z`;
  const toIso = `${to}T23:59:59Z`;

  const setParam = (key: string, value: string | null) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value === null) next.delete(key);
      else next.set(key, value);
      return next;
    });
  };

  const query = useQuery<UsageResponse, ApiError>({
    queryKey: ["admin", "usage", { from, to, groupBy, serviceOnly }],
    queryFn: () => {
      const sp = new URLSearchParams();
      sp.set("from", fromIso);
      sp.set("to", toIso);
      sp.set("group_by", groupBy);
      if (serviceOnly) sp.set("service_only", "true");
      return api<UsageResponse>(`/admin/usage?${sp.toString()}`);
    },
  });

  const download = async (format: "csv" | "json") => {
    try {
      const sp = new URLSearchParams();
      sp.set("from", fromIso);
      sp.set("to", toIso);
      sp.set("group_by", groupBy);
      if (serviceOnly) sp.set("service_only", "true");
      const blob = await apiBlob(`/admin/usage.${format}?${sp.toString()}`);
      triggerDownload(`usage-${from}-${to}.${format}`, blob);
    } catch (err) {
      toast({
        title: "下載失敗",
        description: err instanceof Error ? err.message : String(err),
        variant: "destructive",
      });
    }
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Usage</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void download("csv")}>
            下載 CSV
          </Button>
          <Button variant="outline" onClick={() => void download("json")}>
            下載 JSON
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 p-4 bg-card rounded-lg border">
        <div>
          <Label htmlFor="from">From</Label>
          <Input
            id="from"
            type="date"
            value={from}
            onChange={(e) => setParam("from", e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="to">To</Label>
          <Input
            id="to"
            type="date"
            value={to}
            onChange={(e) => setParam("to", e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="group_by">Group by</Label>
          <Select value={groupBy} onValueChange={(v) => setParam("group_by", v)}>
            <SelectTrigger id="group_by" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="member">Member</SelectItem>
              <SelectItem value="allocation">Allocation</SelectItem>
              <SelectItem value="model">Model</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2 pl-3">
          <Switch
            id="service_only"
            checked={serviceOnly}
            onCheckedChange={(checked) => setParam("service_only", checked ? "true" : null)}
          />
          <Label htmlFor="service_only">只看服務型</Label>
        </div>
      </div>

      {query.isLoading && <p className="text-muted-foreground">載入中…</p>}
      {query.error && (
        <Alert variant="destructive">
          <AlertDescription>
            {query.error.code === "invalid_time_range"
              ? "時間區間不合法"
              : query.error.message}
          </AlertDescription>
        </Alert>
      )}

      {query.data && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                {groupBy === "member" && "Member"}
                {groupBy === "allocation" && "Allocation"}
                {groupBy === "model" && "Model"}
              </TableHead>
              <TableHead className="text-right">Prompt tokens</TableHead>
              <TableHead className="text-right">Completion tokens</TableHead>
              <TableHead className="text-right">Total tokens</TableHead>
              <TableHead className="text-right">Cost (USD)</TableHead>
              <TableHead className="text-right">Calls</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.data.items.map((it) => (
              <TableRow key={it.group_key}>
                <TableCell className="font-medium">{it.display_name ?? it.group_key}</TableCell>
                <TableCell className="text-right">{it.prompt_tokens.toLocaleString()}</TableCell>
                <TableCell className="text-right">{it.completion_tokens.toLocaleString()}</TableCell>
                <TableCell className="text-right">{it.total_tokens.toLocaleString()}</TableCell>
                <TableCell className="text-right">${it.total_cost_usd.toFixed(4)}</TableCell>
                <TableCell className="text-right">{it.call_count}</TableCell>
              </TableRow>
            ))}
            {query.data.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                  此區間沒有使用紀錄
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
