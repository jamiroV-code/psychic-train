"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { OwlMark } from "@/components/brand/OwlMark";

/**
 * The persistent shell navigation — previously the app had none at all, and the
 * only way between the five routes was the home page's list of links or the
 * browser back button.
 *
 * Deliberately NOT included: the per-route data-health pip shown in the
 * Direction D mock-up. There is no endpoint that aggregates per-surface data
 * health yet, and rendering a plausible-looking dot from nothing would be
 * exactly the silently-wrong UI this project forbids. It returns when a real
 * source exists.
 */
const ROUTES = [
  { href: "/screener", label: "Screener" },
  { href: "/regime", label: "Regime" },
  { href: "/narrative", label: "Narrative" },
  { href: "/pairs", label: "Pairs" },
  { href: "/onchain", label: "On-chain" },
] as const;

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="app-rail" aria-label="Main">
      <Link href="/" className="app-rail__brand">
        <OwlMark size={24} tone="dark" />
        <span className="app-rail__wordmark">my_site</span>
      </Link>

      {ROUTES.map((route) => {
        // `/pairs` must stay current on `/pairs/BTC/ETH` too.
        const active = pathname === route.href || pathname.startsWith(`${route.href}/`);
        return (
          <Link
            key={route.href}
            href={route.href}
            className="app-rail__link"
            aria-current={active ? "page" : undefined}
            data-testid={`nav-link-${route.href.slice(1)}`}
          >
            {route.label}
          </Link>
        );
      })}
    </nav>
  );
}
