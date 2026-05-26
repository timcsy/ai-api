import { Navigate, Route } from "react-router-dom";

/**
 * Phase 5.1 — admin URL consolidation.
 *
 * Old (Phase 5) URLs continue to work for bookmarked deep links.
 * Each entry redirects to the new consolidated location.
 *
 * Returning React elements (rather than an array of objects) keeps the
 * call site compatible with both `<Routes>` and React Router's `useRoutes`.
 */
const REDIRECTS: Array<{ from: string; to: string }> = [
  { from: "/admin/catalog-manage", to: "/admin/model" },
  { from: "/admin/model-access", to: "/admin/model" },
  { from: "/admin/catalog", to: "/admin/model" },
  { from: "/admin/allocations", to: "/admin/observability/allocations" },
  { from: "/admin/tags", to: "/admin/tag" },
  { from: "/admin/usage", to: "/admin/observability/usage" },
  { from: "/admin/quota-pool", to: "/admin/observability/quota" },
  { from: "/admin/rebalance-log", to: "/admin/observability/rebalance" },
  { from: "/admin/audit", to: "/admin/observability/audit" },
];

export function LegacyRedirectRoutes() {
  return REDIRECTS.map(({ from, to }) => (
    <Route key={from} path={from} element={<Navigate to={to} replace />} />
  ));
}
