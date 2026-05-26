import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { VisibilityDiagnose } from "@/components/visibility-diagnose";
import { ApiError, api } from "@/lib/api-client";

interface AdminMember {
  id: string;
  email: string;
  provider: string;
  status: string;
  is_admin: boolean;
  created_at: string;
}

interface AdminAllocation {
  id: string;
  member_id: string;
  resource_model: string;
  status: string;
  quota_tokens_per_month: number | null;
  token_prefix: string;
  created_at: string;
}

interface VisibleModel {
  slug: string;
  display_name: string;
  provider: string;
}

export function AdminMemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const memberId = id ?? "";

  const membersQuery = useQuery<AdminMember[], ApiError>({
    queryKey: ["admin", "members"],
    queryFn: () => api<AdminMember[]>("/admin/members"),
  });
  const member = membersQuery.data?.find((m) => m.id === memberId);

  const tagsQuery = useQuery<string[], ApiError>({
    queryKey: ["admin", "members", memberId, "tags"],
    queryFn: () => api<string[]>(`/admin/members/${memberId}/tags`),
    enabled: !!memberId,
  });

  const visibleQuery = useQuery<VisibleModel[], ApiError>({
    queryKey: ["admin", "members", memberId, "visible-models"],
    queryFn: () => api<VisibleModel[]>(`/admin/members/${memberId}/visible-models`),
    enabled: !!memberId && member?.status === "active",
  });

  const allocsQuery = useQuery<AdminAllocation[], ApiError>({
    queryKey: ["admin", "allocations"],
    queryFn: () => api<AdminAllocation[]>("/admin/allocations"),
  });
  const memberAllocs = (allocsQuery.data ?? []).filter((a) => a.member_id === memberId);

  if (membersQuery.isLoading) return <div className="container mx-auto py-8">載入中…</div>;
  if (!member) {
    return (
      <div className="container mx-auto py-8 max-w-3xl space-y-4">
        <p>找不到 member id「{memberId}」</p>
        <Button asChild variant="outline"><Link to="/admin/member">回成員列表</Link></Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-3xl space-y-4">
      <div className="text-sm">
        <Link to="/admin/member" className="text-muted-foreground hover:underline">← 回成員</Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{member.email}</CardTitle>
          <CardDescription className="font-mono text-xs">{member.id}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div><span className="text-muted-foreground">登入方式：</span>{member.provider}</div>
            <div>
              <span className="text-muted-foreground">狀態：</span>
              <Badge variant={member.status === "active" ? "default" : "secondary"}>
                {member.status}
              </Badge>
            </div>
            <div>
              <span className="text-muted-foreground">管理員：</span>
              {member.is_admin ? <Badge>是</Badge> : <span className="text-muted-foreground">否</span>}
            </div>
            <div className="col-span-3 text-xs text-muted-foreground">
              建立於 {new Date(member.created_at).toLocaleString("zh-TW")}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Tag</CardTitle>
          <CardDescription>到「成員」列表 inline 編輯；此處檢視用</CardDescription>
        </CardHeader>
        <CardContent>
          {tagsQuery.data?.length === 0 ? (
            <p className="text-sm text-muted-foreground">無 tag</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {tagsQuery.data?.map((t) => (
                <Badge key={t} variant="secondary" className="text-xs">
                  <Link to={`/admin/tag/${t}`} className="hover:underline">{t}</Link>
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">可用 Model</CardTitle>
          <CardDescription>
            該 member 通過 credential gate ∩ access policy 後實際看得到的清單
          </CardDescription>
        </CardHeader>
        <CardContent>
          {visibleQuery.isLoading && <p className="text-sm">載入中…</p>}
          {visibleQuery.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">該 member 目前看不到任何 model</p>
          )}
          {(visibleQuery.data ?? []).length > 0 && (
            <ul className="text-sm space-y-1">
              {visibleQuery.data?.map((m) => (
                <li key={m.slug}>
                  <Link to={`/admin/model/${m.slug}`} className="font-mono text-xs text-primary hover:underline">
                    {m.slug}
                  </Link>
                  <span className="ml-2 text-muted-foreground">{m.display_name}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3">
            <VisibilityDiagnose memberId={memberId} compact />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Allocations</CardTitle>
          <CardDescription>該 member 的所有分配</CardDescription>
        </CardHeader>
        <CardContent>
          {memberAllocs.length === 0 ? (
            <p className="text-sm text-muted-foreground">無 allocation</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>模型</TableHead>
                  <TableHead>狀態</TableHead>
                  <TableHead>配額</TableHead>
                  <TableHead>Token</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {memberAllocs.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="font-mono text-xs">{a.resource_model}</TableCell>
                    <TableCell>
                      <Badge variant={a.status === "active" ? "default" : "secondary"}>{a.status}</Badge>
                    </TableCell>
                    <TableCell>{a.quota_tokens_per_month ?? "無限額"}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{a.token_prefix}…</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <p className="text-xs text-muted-foreground mt-2">
            建立 / 撤回等動作在「成員」列表（建分配 dialog）；後續可內嵌至此頁。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
