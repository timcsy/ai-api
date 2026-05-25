import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api-client";

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

  const activeProviders = providers.data?.filter((p) => p.status === "active") ?? [];
  const activeMembers = members.data?.filter((m) => m.status === "active") ?? [];
  const totalModels = models.data?.length ?? 0;
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
      to: "/admin/catalog-manage",
      cta: "去 Catalog 管理",
    },
    {
      done: activeMembers.length > 0,
      label: "建立成員（或設定自動註冊）",
      description:
        activeMembers.length > 0
          ? `有 ${activeMembers.length} 個 active member`
          : "沒有 active member；google SSO 或 local password 兩種方式",
      to: "/admin/members",
      cta: "去成員管理",
    },
    {
      done: totalAllocations > 0,
      label: "建立成員的 Allocation（發 token）",
      description:
        totalAllocations > 0
          ? `已建立 ${totalAllocations} 筆 allocation`
          : "成員需要 allocation token 才能呼叫 proxy",
      to: "/admin/allocations",
      cta: "去分配管理",
    },
  ];

  const doneCount = checklist.filter((x) => x.done).length;
  const allReady = doneCount === checklist.length;

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
              到「Catalog 管理」看每個 model 的可見性。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm">
              <Link to="/admin/catalog-manage">去 Catalog 管理</Link>
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
            <Link className="text-primary hover:underline" to="/admin/quota-pool">配額池</Link>
            <Link className="text-primary hover:underline" to="/admin/rebalance-log">Rebalance 記錄</Link>
            <Link className="text-primary hover:underline" to="/admin/audit">稽核紀錄</Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
