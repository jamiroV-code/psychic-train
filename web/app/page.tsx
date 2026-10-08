import Link from "next/link";
import { OwlMark } from "@/components/brand/OwlMark";

// The five surfaces, in the same order as the shell navigation. The
// `data-testid` values are unchanged — two E2E specs click through them.
const AREAS = [
  {
    href: "/screener",
    testId: "home-link-screener",
    label: "Screener",
    blurb: "Price charts and gain chips across the watchlist.",
  },
  {
    href: "/regime",
    testId: "home-link-regime",
    label: "Regime",
    blurb: "Six liquidity components and a reproduced composite, shown against LiqTide's own index.",
  },
  {
    href: "/narrative",
    testId: "home-link-narrative",
    label: "Narrative",
    blurb: "Attention by narrative from free proxies — a deliberately weaker signal than price.",
  },
  {
    href: "/pairs",
    testId: "home-link-pairs",
    label: "Pair screener",
    blurb: "Every pair in an 18-coin universe tested for cointegration. Diagnostic, never a live signal.",
  },
  {
    href: "/onchain",
    testId: "home-link-onchain",
    label: "On-chain growth",
    blurb: "Participant growth per chain, with each source and counting method stated on the panel.",
  },
] as const;

export default function HomePage() {
  return (
    <main>
      <header className="home-head">
        <OwlMark size={44} tone="dark" />
        <div>
          <h1>my_site</h1>
          <p className="home-sub">
            Market research tooling. Every number is computed once in Python and rendered here —
            never recalculated, never silently filled in.
          </p>
        </div>
      </header>

      <div className="home-grid">
        {AREAS.map((area) => (
          <Link key={area.href} href={area.href} data-testid={area.testId} className="home-card">
            <span className="home-card__label">{area.label}</span>
            <span className="home-card__blurb">{area.blurb}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
