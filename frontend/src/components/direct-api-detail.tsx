import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { UsageExplorer } from "@/components/usage-explorer";
import { apiBaseUrl } from "@/lib/api-base";
import { useCatalogModels } from "@/lib/catalog-models";

/** Phase 34 (049): the "直接用 API / SDK" application — for members who write code.
 * Pick any model you can access → see a copy-paste example (curl / Python / JS),
 * reusing the single shared ApiUsageExample. */
export function DirectApiDetail() {
  const catalog = useCatalogModels();
  const models = catalog.models.map((m) => ({
    slug: m.slug,
    label: m.displayName ?? m.slug,
    kind: m.kind,
    supportsResponses: m.supportsResponses,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">直接用 API / SDK</CardTitle>
        <CardDescription>
          平台是 OpenAI 相容的——用任何會講 OpenAI API 的程式/SDK 指向{" "}
          <code className="text-xs break-all">{apiBaseUrl()}</code>，帶上你的金鑰即可。
          選一個模型看可複製的範例；把 <code className="text-xs">$TOKEN</code> 換成你的金鑰 token。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <UsageExplorer
          models={models}
          emptyHint={
            catalog.isLoading
              ? "載入模型中…"
              : "目前沒有你可用的模型。請先在「分配」領取，或請管理員授予。"
          }
        />
      </CardContent>
    </Card>
  );
}
