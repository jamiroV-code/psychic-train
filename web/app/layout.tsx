import type { ReactNode } from "react";

export const metadata = {
  title: "Momentum Screener",
  description: "Watchlist-driven momentum screener board",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
