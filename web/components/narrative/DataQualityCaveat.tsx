/**
 * Plain-language data-quality caveat (ADR-9, AC-11). Static text, rendered at
 * the top of /narrative and again on each of the three views so it is never
 * scrolled out of sight of the numbers it qualifies.
 */
export function DataQualityCaveat({ view }: { view: "page" | "history" | "comparison" | "change" }) {
  return (
    <aside
      data-testid={`narrative-caveat-${view}`}
      role="note"
      style={{ fontSize: 12, color: "#8a8f98", borderLeft: "3px solid #ff9800", padding: "4px 8px", margin: "6px 0" }}
    >
      <strong>Data quality:</strong> these are unofficial, free attention proxies (Google Trends, Reddit,
      CoinGecko, Hyperliquid). Each source is normalised within itself, so levels are not comparable across
      providers. Treat this as a weaker signal than price — give it lower weight.
    </aside>
  );
}
