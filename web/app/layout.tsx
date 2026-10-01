import type { ReactNode } from "react";
import "./globals.css";
import { AppNav } from "@/components/shell/AppNav";

export const metadata = {
  // `%s` lets each route set its own tab title. Before this, all six pages
  // shared the title "Momentum Screener" — the name of one of the five areas,
  // used as the name of the whole app.
  title: {
    default: "my_site",
    template: "%s · my_site",
  },
  description: "Market research tooling: screener, regime, narrative, pairs and on-chain growth.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="terminus">
      <body>
        <div className="app-shell">
          <AppNav />
          <div className="app-main">{children}</div>
        </div>
      </body>
    </html>
  );
}
