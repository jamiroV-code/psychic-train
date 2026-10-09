import { ScreenerBoard } from "@/components/screener/ScreenerBoard";

export const metadata = { title: "Screener" };

export default function ScreenerPage() {
  return (
    <main>
      <h1>Screener</h1>
      {/* T37 / S6: the board hosts the spaghetti chart, which follows its timeframe. */}
      <ScreenerBoard />
    </main>
  );
}
