/**
 * Phase 5.1 — Model entry page.
 *
 * Reuses the existing catalog-manage list (with provider health column,
 * visibility column, create/delete) since it already shows everything an
 * admin needs at the list level. Each row links to /admin/model/:slug for
 * the consolidated detail (basic + access policy + diagnosis).
 */
export { AdminCatalogManagePage as AdminModelPage } from "./catalog-manage";
