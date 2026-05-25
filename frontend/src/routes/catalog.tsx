import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  buildCatalogQueryKey,
  buildCatalogQueryString,
  useCatalogFilters,
  type ListFilter,
} from "@/hooks/use-catalog-filters";
import { ApiError, api } from "@/lib/api-client";

interface Model {
  slug: string;
  display_name: string;
  family: string;
  description: string;
  modality_input: string[];
  modality_output: string[];
  capabilities: string[];
  cost_tier: string;
  recommended_for: string[];
  tags: string[];
  status: string;
}

interface Facets {
  modality_input: Record<string, number>;
  modality_output: Record<string, number>;
  capabilities: Record<string, number>;
  cost_tier: Record<string, number>;
  recommended_for: Record<string, number>;
  family: Record<string, number>;
  tags: Record<string, number>;
}

function FacetSection({
  title,
  values,
  selected,
  onToggle,
  filterKey,
}: {
  title: string;
  values: Record<string, number>;
  selected: string[];
  onToggle: (key: ListFilter, value: string) => void;
  filterKey: ListFilter;
}) {
  const entries = Object.entries(values).sort((a, b) => b[1] - a[1]);
  // Hide facet group when there's nothing to choose between: 0 values, or a
  // single value (which would just echo "this is the only option").
  if (entries.length <= 1) return null;
  return (
    <div className="space-y-1.5">
      <h3 className="text-sm font-semibold">{title}</h3>
      {entries.map(([value, count]) => {
        const id = `${filterKey}-${value}`;
        return (
          <div key={value} className="flex items-center space-x-2">
            <Checkbox
              id={id}
              checked={selected.includes(value)}
              onCheckedChange={() => onToggle(filterKey, value)}
            />
            <Label htmlFor={id} className="text-sm cursor-pointer flex-1 capitalize">
              {value}
            </Label>
            <span className="text-xs text-muted-foreground">({count})</span>
          </div>
        );
      })}
    </div>
  );
}

export function CatalogPage() {
  const { filters, toggleList, setCostTier, setIncludeDeprecated, clear } = useCatalogFilters();

  const facetsQuery = useQuery<Facets, ApiError>({
    queryKey: ["catalog", "filters"],
    queryFn: () => api<Facets>("/catalog/filters"),
    staleTime: 5 * 60_000,
  });

  const modelsQuery = useQuery<Model[], ApiError>({
    queryKey: buildCatalogQueryKey(filters),
    queryFn: () => api<Model[]>(`/catalog/models${buildCatalogQueryString(filters)}`),
    staleTime: 5 * 60_000,
  });

  return (
    <div className="container mx-auto py-8 grid grid-cols-1 md:grid-cols-[260px_1fr] gap-6">
      {/* Sidebar */}
      <aside>
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">篩選</CardTitle>
              <button onClick={clear} className="text-xs text-muted-foreground hover:underline">
                清除
              </button>
            </div>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[60vh] pr-3">
              <div className="space-y-5">
                <div className="flex items-center space-x-2">
                  <Switch
                    id="include-deprecated"
                    checked={filters.include_deprecated}
                    onCheckedChange={setIncludeDeprecated}
                  />
                  <Label htmlFor="include-deprecated" className="text-sm">
                    含已停用
                  </Label>
                </div>
                <Separator />

                {facetsQuery.data && (
                  <>
                    <FacetSection
                      title="輸入模態"
                      values={facetsQuery.data.modality_input}
                      selected={filters.modality_input}
                      onToggle={toggleList}
                      filterKey="modality_input"
                    />
                    <FacetSection
                      title="輸出模態"
                      values={facetsQuery.data.modality_output}
                      selected={filters.modality_output}
                      onToggle={toggleList}
                      filterKey="modality_output"
                    />
                    <FacetSection
                      title="能力"
                      values={facetsQuery.data.capabilities}
                      selected={filters.capability}
                      onToggle={toggleList}
                      filterKey="capability"
                    />
                    {Object.keys(facetsQuery.data.cost_tier).length > 1 && (
                    <div className="space-y-1.5">
                      <h3 className="text-sm font-semibold">成本等級</h3>
                      {Object.entries(facetsQuery.data.cost_tier)
                        .sort((a, b) => b[1] - a[1])
                        .map(([tier, count]) => {
                          const id = `cost-${tier}`;
                          const checked = filters.cost_tier === tier;
                          return (
                            <div key={tier} className="flex items-center space-x-2">
                              <Checkbox
                                id={id}
                                checked={checked}
                                onCheckedChange={() => setCostTier(checked ? null : tier)}
                              />
                              <Label htmlFor={id} className="text-sm cursor-pointer flex-1 capitalize">
                                {tier}
                              </Label>
                              <span className="text-xs text-muted-foreground">({count})</span>
                            </div>
                          );
                        })}
                    </div>
                    )}
                    <FacetSection
                      title="適用情境"
                      values={facetsQuery.data.recommended_for}
                      selected={filters.recommended_for}
                      onToggle={toggleList}
                      filterKey="recommended_for"
                    />
                  </>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </aside>

      {/* Grid */}
      <section>
        <h1 className="text-2xl font-bold mb-4">模型目錄</h1>
        {modelsQuery.isLoading && <p className="text-muted-foreground">載入中…</p>}
        {modelsQuery.error && (
          <Alert variant="destructive">
            <AlertDescription>無法載入：{modelsQuery.error.message}</AlertDescription>
          </Alert>
        )}
        {modelsQuery.data && modelsQuery.data.length === 0 && (
          <Card>
            <CardContent className="py-10 text-center text-muted-foreground">
              沒有符合條件的模型，請放寬 filter。
            </CardContent>
          </Card>
        )}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {modelsQuery.data?.map((m) => (
            <Link key={m.slug} to={`/catalog/${m.slug}`}>
              <Card className="hover:bg-accent transition-colors cursor-pointer h-full">
                <CardHeader>
                  <div className="flex items-center justify-between mb-1">
                    <CardTitle className="text-lg">{m.display_name}</CardTitle>
                    <Badge variant="outline">{m.cost_tier}</Badge>
                  </div>
                  <CardDescription className="text-xs">
                    <Badge variant="secondary" className="mr-1">{m.family}</Badge>
                    {m.modality_input.join(" / ")} → {m.modality_output.join(" / ")}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm line-clamp-3 text-muted-foreground">
                    {m.description.split("\n")[0]}
                  </p>
                  {m.recommended_for.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {m.recommended_for.slice(0, 4).map((r) => (
                        <Badge key={r} variant="outline" className="text-[10px]">
                          {r}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
