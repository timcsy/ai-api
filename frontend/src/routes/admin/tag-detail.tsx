import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api-client";

interface AdminMember {
  id: string;
  email: string;
  status: string;
}

interface CatalogModel {
  slug: string;
  display_name: string;
  provider: string;
  default_access: "open" | "restricted";
  allowed_tags: string[];
  denied_tags: string[];
}

export function AdminTagDetailPage() {
  const { name } = useParams<{ name: string }>();
  const tagName = name ?? "";

  const allMembersQuery = useQuery<AdminMember[], ApiError>({
    queryKey: ["admin", "members"],
    queryFn: () => api<AdminMember[]>("/admin/members"),
  });

  const memberTagsQuery = useQuery<{ memberId: string; tags: string[] }[], ApiError>({
    queryKey: ["admin", "all-member-tags"],
    queryFn: async () => {
      const ms = await api<AdminMember[]>("/admin/members");
      return Promise.all(
        ms.map(async (m) => ({
          memberId: m.id,
          tags: await api<string[]>(`/admin/members/${m.id}/tags`),
        })),
      );
    },
  });

  const modelsQuery = useQuery<CatalogModel[], ApiError>({
    queryKey: ["admin", "catalog-models-admin"],
    queryFn: () => api<CatalogModel[]>("/admin/catalog/models"),
  });

  const holdingMembers = (memberTagsQuery.data ?? [])
    .filter((row) => row.tags.includes(tagName))
    .map((row) => allMembersQuery.data?.find((m) => m.id === row.memberId))
    .filter((m): m is AdminMember => m !== undefined);

  const allowingModels = (modelsQuery.data ?? []).filter((m) => m.allowed_tags.includes(tagName));
  const denyingModels = (modelsQuery.data ?? []).filter((m) => m.denied_tags.includes(tagName));

  return (
    <div className="container mx-auto py-8 max-w-3xl space-y-4">
      <div className="text-sm">
        <Link to="/admin/tag" className="text-muted-foreground hover:underline">← 回 Tag</Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Tag：<code>{tagName}</code></CardTitle>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">持有此 tag 的成員（{holdingMembers.length}）</CardTitle>
          <CardDescription>到「成員」列表 inline 編輯加 / 移除 tag</CardDescription>
        </CardHeader>
        <CardContent>
          {holdingMembers.length === 0 ? (
            <p className="text-sm text-muted-foreground">無人持有</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {holdingMembers.map((m) => (
                <li key={m.id}>
                  <Link to={`/admin/member/${m.id}`} className="text-primary hover:underline">
                    {m.email}
                  </Link>
                  {m.status !== "active" && (
                    <Badge variant="outline" className="ml-2 text-xs">{m.status}</Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
          <Button asChild variant="link" size="sm" className="mt-2 px-0">
            <Link to="/admin/member">去成員列表編輯</Link>
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">將此 tag 列為 Allowed 的 Model（{allowingModels.length}）</CardTitle>
        </CardHeader>
        <CardContent>
          {allowingModels.length === 0 ? (
            <p className="text-sm text-muted-foreground">無</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {allowingModels.map((m) => (
                <li key={m.slug}>
                  <Link to={`/admin/model/${m.slug}`} className="font-mono text-xs text-primary hover:underline">
                    {m.slug}
                  </Link>
                  <span className="ml-2 text-muted-foreground">{m.display_name}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">將此 tag 列為 Denied 的 Model（{denyingModels.length}）</CardTitle>
        </CardHeader>
        <CardContent>
          {denyingModels.length === 0 ? (
            <p className="text-sm text-muted-foreground">無</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {denyingModels.map((m) => (
                <li key={m.slug}>
                  <Link to={`/admin/model/${m.slug}`} className="font-mono text-xs text-primary hover:underline">
                    {m.slug}
                  </Link>
                  <span className="ml-2 text-muted-foreground">{m.display_name}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
