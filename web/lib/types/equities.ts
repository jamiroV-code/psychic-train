import type { RefreshStatus } from "@/lib/types/refresh";

// T50 / S9E: GET /api/equities/status, the crypto status keys plus the
// newest daily bar date over the equities list (`YYYY-MM-DD`, or null when
// nothing is cached).
export interface EquitiesStatus extends RefreshStatus {
  last_bar_date?: string | null;
}
