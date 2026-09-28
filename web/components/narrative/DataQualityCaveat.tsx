/**
 * Plain-language data-quality caveat (v1 ADR-9, AC-11). Static text, rendered
 * exactly once per /narrative page, pinned (sticky) by NarrativeDashboard so it
 * stays in view while scrolling (v2 ADR-6, AC-12) — not repeated per view.
 */
export function DataQualityCaveat({ view }: { view: "page" }) {
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
