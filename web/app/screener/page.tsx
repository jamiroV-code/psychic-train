import { BtcLegChart } from "@/components/screener/BtcLegChart";
import { FreshnessStrip } from "@/components/screener/FreshnessStrip";
import { LiveProvider } from "@/components/screener/LiveProvider";
import { ScreenerBoard } from "@/components/screener/ScreenerBoard";

export const metadata = { title: "Screener" };

export default function ScreenerPage() {
  return (
    <main>
      <h1>Screener</h1>
      {/* T43 / S11b: one live poller for the page; the strip says how fresh it is. */}
      <LiveProvider>
        <FreshnessStrip />
        {/* T38 / S7: BTC daily history with confirmed legs, above the board. */}
        <BtcLegChart />
        {/* T37 / S6: the board hosts the spaghetti chart, which follows its timeframe. */}
        <ScreenerBoard />
      </LiveProvider>
    </main>
  );
}
