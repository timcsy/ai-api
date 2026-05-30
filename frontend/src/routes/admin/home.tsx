import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api-client";

interface AuditRow {
  id: string;
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  target_type: string | null;
  target_id: string | null;
  created_at: string;
}

interface ProviderCredential {
  id: string;
  provider: string;
  status: string;
}
interface AdminMember {
  id: string;
  status: string;
}
interface CatalogModel {
  slug: string;
  visibility: {
    provider_has_credential: boolean;
    visible_member_count: number;
    total_active_members: number;
  };
}
interface AdminAllocation {
  id: string;
  status: string;
}

export function AdminHomePage() {
  const providers = useQuery<ProviderCredential[], ApiError>({
    queryKey: ["admin", "providers"],
    queryFn: () => api<ProviderCredential[]>("/admin/providers"),
  });
  const members = useQuery<AdminMember[], ApiError>({
    queryKey: ["admin", "members"],
    queryFn: () => api<AdminMember[]>("/admin/members"),
  });
  const models = useQuery<CatalogModel[], ApiError>({
    queryKey: ["admin", "catalog-models-admin"],
    queryFn: () => api<CatalogModel[]>("/admin/catalog/models"),
  });
  const allocations = useQuery<AdminAllocation[], ApiError>({
    queryKey: ["admin", "allocations"],
    queryFn: () => api<AdminAllocation[]>("/admin/allocations"),
  });

  // Phase 5.1: if all four entities have ≥1 row, switch from onboarding to dashboard mode.
  const audit = useQuery<{ rows: AuditRow[] }, ApiError>({
    queryKey: ["admin", "audit-recent"],
    queryFn: () => api<{ rows: AuditRow[] }>("/admin/audit?limit=10"),
  });

  const activeProviders = providers.data?.filter((p) => p.status === "active") ?? [];
  const activeMembers = members.data?.filter((m) => m.status === "active") ?? [];
  const totalModels = models.data?.length ?? 0;
  const totalAllocs = allocations.data?.length ?? 0;
  const ready =
    activeProviders.length > 0 && totalModels > 0 && activeMembers.length > 0 && totalAllocs > 0;
  const hiddenModels =
    models.data?.filter((m) => m.visibility.visible_member_count === 0).length ?? 0;
  const totalAllocations = allocations.data?.length ?? 0;

  const checklist: Array<{
    done: boolean;
    label: string;
    description: string;
    to: string;
    cta: string;
  }> = [
    {
      done: activeProviders.length > 0,
      label: "新增至少一筆 Provider 憑證",
      description:
        activeProviders.length > 0
          ? `已有 ${activeProviders.length} 筆 active credential`
          : "沒有 credential，所有 model 對成員都隱藏",
      to: "/admin/providers",
      cta: "去 Provider 憑證",
    },
    {
      done: totalModels > 0,
      label: "在 Catalog 加入 Model",
      description:
        totalModels > 0
          ? `Catalog 有 ${totalModels} 個 model（${hiddenModels} 個對 member 隱藏）`
          : "Catalog 是空的；先加入至少 1 個 model member 才有東西可用",
      to: "/admin/model",
      cta: "去 Model",
    },
    {
      done: activeMembers.length > 0,
      label: "建立成員（或設定自動註冊）",
      description:
        activeMembers.length > 0
          ? `有 ${activeMembers.length} 個 active member`
          : "沒有 active member；google SSO 或 local password 兩種方式",
      to: "/admin/member",
      cta: "去成員",
    },
    {
      done: totalAllocations > 0,
      label: "建立成員的 Allocation（發 token）",
      description:
        totalAllocations > 0
          ? `已建立 ${totalAllocations} 筆 allocation`
          : "成員需要 allocation token 才能呼叫 proxy",
      to: "/admin/member",
      cta: "去成員（建立分配）",
    },
  ];

  const doneCount = checklist.filter((x) => x.done).length;
  const allReady = doneCount === checklist.length;

  const quarantinedCount = (allocations.data ?? []).filter((a) => a.status === "quarantined").length;
  const pausedCount = (allocations.data ?? []).filter((a) => a.status === "paused").length;

  // Phase 5.1: switch to dashboard mode when fully onboarded
  if (ready) {
    return (
      <Dashboard
        hiddenModels={hiddenModels}
        audit={audit.data?.rows ?? []}
        quarantinedCount={quarantinedCount}
        pausedCount={pausedCount}
      />
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-4xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">管理員首頁</h1>
        <p className="text-muted-foreground mt-1">
          {allReady ? "✓ 所有基礎設定完成。" : `進度：${doneCount}/${checklist.length}`}
        </p>
      </div>

      {hiddenModels > 0 && (
        <Card className="border-amber-500">
          <CardHeader>
            <CardTitle className="text-base text-amber-900">
              ⚠ {hiddenModels} 個 model 對成員隱藏
            </CardTitle>
            <CardDescription>
              可能原因：對應 provider 沒有 active credential、或 access policy 沒命中任何 member。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm">
              <Link to="/admin/model">去 Model</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">設定清單</CardTitle>
          <CardDescription>建議按順序完成</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {checklist.map((item) => (
            <div
              key={item.to}
              className="flex items-start justify-between gap-3 border rounded-md p-3"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <Badge variant={item.done ? "default" : "outline"}>
                    {item.done ? "✓" : "?"}
                  </Badge>
                  <h3 className="font-medium">{item.label}</h3>
                </div>
                <p className="text-sm text-muted-foreground mt-1">{item.description}</p>
              </div>
              <Button asChild size="sm" variant={item.done ? "outline" : "default"}>
                <Link to={item.to}>{item.cta}</Link>
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">其他管理頁面</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
            <Link className="text-primary hover:underline" to="/admin/tags">Tag 管理</Link>
            <Link className="text-primary hover:underline" to="/admin/model-access">Model 存取規則</Link>
            <Link className="text-primary hover:underline" to="/admin/usage">用量</Link>
            <Link className="text-primary hover:underline" to="/admin/observability/quota">配額池</Link>
            <Link className="text-primary hover:underline" to="/admin/observability/rebalance">Rebalance 記錄</Link>
            <Link className="text-primary hover:underline" to="/admin/observability/audit">稽核紀錄</Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Dashboard({
  hiddenModels, audit, quarantinedCount, pausedCount,
}: {
  hiddenModels: number;
  audit: AuditRow[];
  quarantinedCount: number;
  pausedCount: number;
}) {
  return (
    <div className="container mx-auto py-8 max-w-4xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold">管理員儀表板</h1>
        <p className="text-muted-foreground mt-1">基礎設定完成。日常維運從這裡開始。</p>
      </div>

      {(quarantinedCount > 0 || pausedCount > 0) && (
        <Card className={quarantinedCount > 0 ? "border-destructive" : "border-amber-500"}>
          <CardHeader>
            <CardTitle className="text-base">
              {quarantinedCount > 0 && <span className="text-destructive">🚨 {quarantinedCount} 個分配被自動隔離</span>}
              {quarantinedCount > 0 && pausedCount > 0 && <span className="text-muted-foreground"> · </span>}
              {pausedCount > 0 && <span className="text-amber-900">⏸ {pausedCount} 個被暫停</span>}
            </CardTitle>
            <CardDescription>
              {quarantinedCount > 0
                ? "被異常偵測器自動隔離（突發用量）。確認後可解除隔離；若為已知 agent/服務用途，可標為「服務型」永久豁免異常偵測。"
                : "有分配處於暫停狀態，使用者目前無法呼叫。"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm">
              <Link to="/admin/observability/allocations">去檢視 / 處理</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {hiddenModels > 0 && (
        <Card className="border-amber-500">
          <CardHeader>
            <CardTitle className="text-base text-amber-900">
              ⚠ {hiddenModels} 個 model 對所有 member 隱藏
            </CardTitle>
            <CardDescription>
              該 model 對應 provider 無 active credential，或 access policy 沒命中任何 member。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm">
              <Link to="/admin/model">去 Model 檢查</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">最近活動</CardTitle>
          <CardDescription>最新 10 條稽核紀錄</CardDescription>
        </CardHeader>
        <CardContent>
          {audit.length === 0 ? (
            <p className="text-sm text-muted-foreground">目前無紀錄。</p>
          ) : (
            <ul className="text-xs space-y-1">
              {audit.map((r) => (
                <li key={r.id} className="flex items-center gap-2">
                  <span className="text-muted-foreground">{new Date(r.created_at).toLocaleString("zh-TW")}</span>
                  <Badge variant="outline" className="font-mono text-xs">{r.event_type}</Badge>
                  <span className="text-muted-foreground">{r.actor_type}{r.actor_id ? ` ${r.actor_id}` : ""}</span>
                </li>
              ))}
            </ul>
          )}
          <Button asChild variant="link" size="sm" className="mt-2 px-0">
            <Link to="/admin/observability/audit">看完整稽核紀錄 →</Link>
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">快速入口</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
            <Link className="text-primary hover:underline" to="/admin/model">Model</Link>
            <Link className="text-primary hover:underline" to="/admin/member">成員</Link>
            <Link className="text-primary hover:underline" to="/admin/tag">Tag</Link>
            <Link className="text-primary hover:underline" to="/admin/providers">Provider 憑證</Link>
            <Link className="text-primary hover:underline" to="/admin/observability/usage">用量</Link>
            <Link className="text-primary hover:underline" to="/admin/observability/quota">配額池</Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
