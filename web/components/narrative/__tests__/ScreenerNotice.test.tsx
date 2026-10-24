import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ScreenerBoard } from "@/components/screener/ScreenerBoard";

vi.mock("@/lib/island-loader", () => ({ loadIslands: () => new Promise(() => undefined) }));
vi.mock("@/lib/use-board-layout", async (orig) => {
  const real = await orig<typeof import("@/lib/use-board-layout")>();
  return {
    ...real,
    useBoardLayout: (...args: Parameters<typeof real.useBoardLayout>) => ({
      ...real.useBoardLayout(...args),
      announcement: "ETH removed. Basket Majors no longer counts it.",
    }),
  };
});

describe("screener removal notice", () => {
  it("is shown to sighted users and the aria-live announcer is kept", () => {
    render(<ScreenerBoard fetchBoard={() => new Promise(() => undefined)} fetchLayout={() => new Promise(() => undefined)} />);
    const visible = screen.getByTestId("board-announcement-visible");
    expect(visible).toHaveAttribute("role", "status");
    expect(visible).toHaveClass("board-notice");
    expect(visible).not.toHaveClass("visually-hidden");
    expect(visible).toHaveTextContent("Basket Majors no longer counts it");
    const announcer = screen.getByTestId("board-announcer");
    expect(announcer).toHaveAttribute("aria-live", "polite");
    expect(announcer).toHaveClass("visually-hidden");
  });
});
