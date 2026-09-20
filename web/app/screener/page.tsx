import { ScreenerBoard } from "@/components/screener/ScreenerBoard";
import { RelativePerformanceChart } from "@/components/screener/RelativePerformanceChart";
import { LegTimelineBanner } from "@/components/screener/LegTimelineBanner";
import { NarrativeStrip } from "@/components/screener/NarrativeStrip";

export default function ScreenerPage() {
  return (
    <main>
      <h1>Screener</h1>
      {/* RFC-002 item 46: its own additive insertion into this page,
          alongside ScreenerBoard/RelativePerformanceChart — not a per-coin
          panel addition (Blast Radius / Parallel-safety note: RFC-003's
          NarrativeStrip is the other additive insertion here, non-
          overlapping with this one). */}
      <LegTimelineBanner />
      {/* RFC-003 item 60: its own additive insertion, non-overlapping with
          LegTimelineBanner above (Parallel-safety note). */}
      <NarrativeStrip />
      <ScreenerBoard />
      {/* Amendment 1 (SPEC US-8): a second, separate view positioned
          alongside (not inside) ScreenerBoard — not a per-coin panel
          addition. */}
      <RelativePerformanceChart />
    </main>
  );
}
