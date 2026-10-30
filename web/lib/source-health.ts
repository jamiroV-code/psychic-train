import type { DiscoverySourceRow } from "@/lib/types/discovery";

export interface HealthLine {
  key: string;
  text: string;
}

export function sourceHealthLines(_row: DiscoverySourceRow): HealthLine[] | null {
  return null;
}
