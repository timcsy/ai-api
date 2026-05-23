import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "@/components/protected-route";
import { AuthProvider } from "@/contexts/auth";
import { HomePage } from "@/routes/home";
import { LoginPage } from "@/routes/login";
import { NotFoundPage } from "@/routes/not-found";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // never retry auth errors — let AuthContext handle redirect
        if (error instanceof Error && error.name === "ApiError") {
          const status = (error as { status?: number }).status;
          if (status === 401 || status === 403) return false;
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
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <HomePage />
                </ProtectedRoute>
              }
            />
            <Route path="/index.html" element={<Navigate to="/" replace />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
