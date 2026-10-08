import { ScreenerBoard } from "@/components/screener/ScreenerBoard";
import { RelativePerformanceChart } from "@/components/screener/RelativePerformanceChart";

export const metadata = { title: "Screener" };

export default function ScreenerPage() {
  return (
    <main>
      <h1>Screener</h1>
      <ScreenerBoard />
      {/* Amendment 1 (SPEC US-8): a second, separate view positioned
          alongside (not inside) ScreenerBoard — not a per-coin panel
          addition. */}
      <RelativePerformanceChart />
    </main>
  );
}
