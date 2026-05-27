import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AdminRoute } from "@/components/admin-route";
import { AppShell } from "@/components/app-shell";
import { ProtectedRoute } from "@/components/protected-route";
import { Toaster } from "@/components/ui/toaster";
import { AuthProvider } from "@/contexts/auth";
import { LegacyRedirectRoutes } from "@/lib/legacy-redirects";
import { AdminAllocationsPage } from "@/routes/admin/allocations";
import { AdminAuditPage } from "@/routes/admin/audit";
import { AdminCatalogManagePage } from "@/routes/admin/catalog-manage";
import { AdminHomePage } from "@/routes/admin/home";
import { AdminMembersPage } from "@/routes/admin/members";
import { AdminMemberDetailPage } from "@/routes/admin/member-detail";
import { AdminModelPage } from "@/routes/admin/model";
import { AdminModelDetailPage } from "@/routes/admin/model-detail";
import { AdminObservabilityPage } from "@/routes/admin/observability";
import { AdminPricesPage } from "@/routes/admin/prices";
import { AdminProvidersPage } from "@/routes/admin/providers";
import { AdminQuotaPoolPage } from "@/routes/admin/quota-pool";
import { AdminTagDetailPage } from "@/routes/admin/tag-detail";
import { AdminTagRulesPage } from "@/routes/admin/tag-rules";
import { AdminTagsPage } from "@/routes/admin/tags";
import {
  AdminRebalanceLogDetailPage,
  AdminRebalanceLogListPage,
} from "@/routes/admin/rebalance-log";
import { AdminUsagePage } from "@/routes/admin/usage";
import { AllocationDetailPage } from "@/routes/allocation-detail";
import { CatalogPage } from "@/routes/catalog";
import { CatalogDetailPage } from "@/routes/catalog-detail";
import { DashboardPage } from "@/routes/dashboard";
import { LoginPage } from "@/routes/login";
import { NotFoundPage } from "@/routes/not-found";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (error instanceof Error && error.name === "ApiError") {
          const s = (error as { status?: number }).status;
          if (s === 401 || s === 403 || s === 404) return false;
        }
        return failureCount < 1;
      },
      staleTime: 30_000,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider queryClient={queryClient}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/dashboard/allocations/:id" element={<AllocationDetailPage />} />
              <Route path="/catalog" element={<CatalogPage />} />
              <Route path="/catalog/*" element={<CatalogDetailPage />} />

              {/* Phase 5.1 — admin routes (consolidated) */}
              <Route element={<AdminRoute />}>
                {/* legacy URLs → new locations (must come before catch-alls) */}
                {LegacyRedirectRoutes()}

                <Route path="/admin" element={<AdminHomePage />} />
                <Route path="/admin/model" element={<AdminModelPage />} />
                <Route path="/admin/model/*" element={<AdminModelDetailPage />} />
                <Route path="/admin/member" element={<AdminMembersPage />} />
                <Route path="/admin/member/:id" element={<AdminMemberDetailPage />} />
                <Route path="/admin/providers" element={<AdminProvidersPage />} />
                <Route path="/admin/tag" element={<AdminTagsPage />} />
                <Route path="/admin/tag/rules" element={<AdminTagRulesPage />} />
                <Route path="/admin/tag/:name" element={<AdminTagDetailPage />} />

                {/* observability hub */}
                <Route path="/admin/observability" element={<AdminObservabilityPage />}>
                  <Route index element={<Navigate to="usage" replace />} />
                  <Route path="usage" element={<AdminUsagePage />} />
                  <Route path="allocations" element={<AdminAllocationsPage />} />
                  <Route path="prices" element={<AdminPricesPage />} />
                  <Route path="quota" element={<AdminQuotaPoolPage />} />
                  <Route path="rebalance" element={<AdminRebalanceLogListPage />} />
                  <Route path="rebalance/:id" element={<AdminRebalanceLogDetailPage />} />
                  <Route path="audit" element={<AdminAuditPage />} />
                </Route>

                {/* legacy entry pages kept as no-nav components for now; nav points to new URLs.
                    These remain accessible so the catalog-manage/model-access deep features
                    aren't lost until the new Model entry is fully built. */}
                <Route path="/admin/_legacy/catalog-manage" element={<AdminCatalogManagePage />} />
              </Route>
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
