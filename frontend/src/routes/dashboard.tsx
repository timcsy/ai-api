import { MemberOverview } from "@/components/member-overview";

/**
 * Phase 22: the dashboard is now a slim overview. Key/allocation/usage
 * management moved to their own top-nav pages (/keys, /allocations, /usage).
 */
export function DashboardPage() {
  return <MemberOverview />;
}
