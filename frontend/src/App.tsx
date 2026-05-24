import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/app-shell";
import { ProtectedRoute } from "@/components/protected-route";
import { Toaster } from "@/components/ui/toaster";
import { AuthProvider } from "@/contexts/auth";
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
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
          <Toaster />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
