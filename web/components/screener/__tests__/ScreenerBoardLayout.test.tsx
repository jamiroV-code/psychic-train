import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveProvider } from "@/components/screener/LiveProvider";
import { ScreenerBoard, type ScreenerBoardProps } from "@/components/screener/ScreenerBoard";
import { LayoutConflictError } from "@/lib/api/layout";
import type { ChartRange, SimpleLinesProps } from "@/lib/island-loader";
import type { Layout, LayoutGroup, LayoutUpdate } from "@/lib/types/layout";
import type { RefreshStatus } from "@/lib/types/refresh";
import type { ChartView, ScreenerBoardResponse, SpaghettiResponse, Timeframe } from "@/lib/types/screener";

// T41 / S5b: the board's groups, coin actions, add and remove, and saved
// line toggles. The island mock is the one from ScreenerBoardLinkedZoom, so
// the shared small-chart zoom (T44) can be checked through every edit.
const island = vi.hoisted(() => {
  type Mount = { target: HTMLElement; props: unknown; update: ReturnType<typeof vi.fn> };
  const mounts: Mount[] = [];
  const mountSimpleLines = vi.fn((target: HTMLElement, props: unknown) => {
    const m: Mount = { target, props, update: vi.fn((next: unknown) => (m.props = next)) };
    mounts.push(m);
    return Object.assign(() => undefined, { update: m.update });
  });
  return { mounts, loadIslands: vi.fn(() => Promise.resolve({ mountSimpleLines })) };
});

vi.mock("@/lib/island-loader", () => ({ loadIslands: island.loadIslands }));

function status(): RefreshStatus {
  return {
    running: true,
    disabled_reason: null,
    interval_seconds: 900,
    last_tick_started: "2026-10-03T14:14:00Z",
    last_tick_finished: "2026-10-03T14:15:00Z",
    last_tick_ok: 10,
    last_tick_failed: 0,
    next_tick_at: "2026-10-03T14:30:00Z",
    queue_depth: 0,
    backoff_seconds: 0,
    server_time: "2026-10-03T14:22:00Z",
  };
}

function coin(symbol: string, available = true) {
  return {
    symbol,
    chart: {
      price: available
        ? [
            { timestamp: "2026-10-02T00:00:00Z", close: 99 },
            { timestamp: "2026-10-03T00:00:00Z", close: 100 },
          ]
        : [],
      sma: [],
      available,
      reason: available ? null : "insufficient-history",
      last_bar_ts: available ? "2026-10-03T00:00:00Z" : null,
      fetched_at: null,
      is_partial: false,
      server_time: null,
      stale: false,
      rsi: [],
    },
    percent_change_by_timeframe: {},
    gain_by_timeframe: {},
    rsi: { value: 50, length: 14, as_of: "2026-10-03T00:00:00Z", reason: null },
  };
}

function board(timeframe: Timeframe, symbols: string[], unavailable: string[] = []): ScreenerBoardResponse {
  return {
    timeframe,
    coins: symbols.map((s) => coin(s, !unavailable.includes(s))),
    server_time: null,
    clock_skew_seconds: 0,
    clock_skew_warning: false,
  } as unknown as ScreenerBoardResponse;
}

function g(id: string, name: string, coins: string[]): LayoutGroup {
  return { id, name, coins };
}

function layout(groups: LayoutGroup[], extra: Partial<Layout> = {}): Layout {
  return {
    version: 1,
    section: "crypto",
    revision: 3,
    saved_at: "2026-10-03T00:00:00Z",
    source: "file",
    groups,
    hidden_lines: [],
    ...extra,
  };
}

/** A small layout server: saves need the stored revision, like the API. */
function layoutServer(initial: Layout) {
  let stored = structuredClone(initial);
  const fetchLayout = vi.fn(async () => structuredClone(stored));
  const saveLayout = vi.fn(async (u: LayoutUpdate) => {
    if (u.revision !== stored.revision) throw new LayoutConflictError("layout changed elsewhere");
    stored = { ...stored, revision: stored.revision + 1, groups: u.groups, hidden_lines: u.hidden_lines, source: "file" };
    return structuredClone(stored);
  });
  return {
    fetchLayout,
    saveLayout,
    get: () => stored,
    set: (next: Layout) => {
      stored = structuredClone(next);
    },
  };
}

const spaghettiResponse = (timeframe: Timeframe): SpaghettiResponse => ({
  timeframe,
  window_cap_bars: 200,
  server_time: null,
  series: [
    {
      symbol: "ETH",
      available: true,
      reason: null,
      points: [
        { timestamp: "2026-10-02T00:00:00Z", close: 0 },
        { timestamp: "2026-10-03T00:00:00Z", close: 1 },
      ],
      window_start: "2026-10-02T00:00:00Z",
      window_end: "2026-10-03T00:00:00Z",
      bars: 2,
      last_bar_ts: "2026-10-03T00:00:00Z",
      stale: false,
    },
  ],
  references: [],
});

let monoNow = 0;

async function advance(ms: number) {
  await act(async () => {
    monoNow += ms;
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function panelOrder(): string[] {
  return screen
    .getAllByTestId(/^coin-panel-/)
    .map((el) => el.getAttribute("data-testid")!.replace("coin-panel-", ""));
}

function panelProps(symbol: string): SimpleLinesProps {
  const m = island.mounts.filter((x) => x.target.closest(`[data-testid="coin-panel-${symbol}"]`)).at(-1);
  if (!m) throw new Error(`no chart for ${symbol}`);
  return m.props as SimpleLinesProps;
}

function zoomFrom(symbol: string, range: ChartRange | null) {
  act(() => {
    panelProps(symbol).onRangeChange?.(range);
  });
}

const RANGE = { from: Date.parse("2026-10-02T06:00:00Z"), to: Date.parse("2026-10-02T18:00:00Z") };

interface Setup extends Partial<ScreenerBoardProps> {
  provider?: boolean;
}

function setup(opts: Setup = {}) {
  const { provider, ...props } = opts;
  const fetchSpaghetti = vi.fn(props.fetchSpaghetti ?? (async (tf: Timeframe) => spaghettiResponse(tf)));
  const fetchChart = vi.fn(
    props.fetchChart ??
      (async (s: string, tf: Timeframe) => ({ symbol: s, timeframe: tf, chart: coin(s).chart }) as unknown as ChartView),
  );
  const el = <ScreenerBoard {...props} fetchSpaghetti={fetchSpaghetti} fetchChart={fetchChart} />;
  render(
    provider ? (
      <LiveProvider fetchStatus={async () => status()} mono={() => monoNow}>
        {el}
      </LiveProvider>
    ) : (
      el
    ),
  );
  return { fetchSpaghetti, fetchChart };
}

function region(name: string) {
  return screen.getByRole("region", { name });
}

beforeEach(() => {
  vi.useFakeTimers();
  monoNow = 0;
  island.mounts.length = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

const THREE = ["BTC", "ETH", "SOL"];

describe("ScreenerBoard layout (T41 / S5b)", () => {
  it("shows no panel and no spaghetti chart until both the board and the layout have answered", async () => {
    let answer: ((l: Layout) => void) | null = null;
    const fetchLayout = vi.fn(() => new Promise<Layout>((resolve) => (answer = resolve)));
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout });
    expect(screen.getByTestId("board-announcer")).toBeInTheDocument();
    expect(screen.getByTestId("layout-notice")).toBeInTheDocument();
    expect(screen.getByTestId("layout-save-error")).toBeInTheDocument();
    await advance(0);
    expect(screen.getByTestId("board-loading")).toHaveAttribute("aria-busy", "true");
    expect(screen.queryAllByTestId(/^coin-panel-/)).toHaveLength(0);
    expect(screen.queryByTestId("spaghetti-chart")).toBeNull();
    await act(async () => answer!(layout([g("main", "Main", THREE)])));
    await advance(0);
    expect(screen.queryByTestId("board-loading")).toBeNull();
    expect(panelOrder()).toEqual(THREE);
    expect(screen.getByTestId("spaghetti-chart")).toBeInTheDocument();
  });

  it("renders the groups in layout order with headings, coin counts and an empty-group message", async () => {
    const server = layoutServer(layout([g("alts", "Alts", ["ETH"]), g("main", "Main", ["SOL", "BTC"]), g("later", "Later", [])]));
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout: server.fetchLayout, saveLayout: server.saveLayout });
    await advance(0);
    const headings = within(screen.getByTestId("screener-board-grid")).getAllByRole("heading", { level: 2 });
    expect(headings.map((h) => h.textContent)).toEqual(["Alts", "Main", "Later"]);
    expect(within(region("Alts")).getByTestId("group-count-alts")).toHaveTextContent("1 coin");
    expect(within(region("Main")).getByTestId("group-count-main")).toHaveTextContent("2 coins");
    expect(within(region("Later")).getByTestId("group-empty-later")).toHaveTextContent("No coins in this group yet.");
    expect(panelOrder()).toEqual(["ETH", "SOL", "BTC"]);
  });

  it("keeps the layout order through a timeframe change, an identical tick and the add retry timers; a timeframe change clears the shared zoom", async () => {
    const server = layoutServer(layout([g("main", "Main", ["SOL", "BTC", "ETH"])]));
    let symbols = THREE;
    const addCoin = vi.fn(async (s: string) => {
      symbols = [...THREE, s];
      return { coins: symbols };
    });
    setup({
      provider: true,
      fetchBoard: async (tf) => board(tf, symbols, ["NEW"]),
      fetchLayout: server.fetchLayout,
      saveLayout: server.saveLayout,
      addCoin,
    });
    await advance(0);
    const recorded = panelOrder();
    expect(recorded).toEqual(["SOL", "BTC", "ETH"]);
    zoomFrom("BTC", RANGE);
    expect(panelProps("ETH").linkedRange).toEqual(RANGE);

    fireEvent.click(screen.getByTestId("timeframe-button-4h"));
    await advance(0);
    expect(panelOrder()).toEqual(recorded);
    for (const s of recorded) expect(panelProps(s).linkedRange).toBeNull();

    await advance(60_000);
    expect(panelOrder()).toEqual(recorded);

    fireEvent.change(screen.getByLabelText("Coin symbol"), { target: { value: "new" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Add coin" }));
    });
    await advance(0);
    await advance(4_000);
    await advance(8_000);
    expect(panelOrder()).toEqual([...recorded, "NEW"]);
  });

  it("a layout that cannot load shows one default group, a notice, disabled editing and a working Retry", async () => {
    const server = layoutServer(layout([g("main", "Main", THREE)]));
    let fail = true;
    const fetchLayout = vi.fn(async () => {
      if (fail) throw new Error("API request failed: /api/layout/crypto -> 500");
      return server.fetchLayout();
    });
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout, saveLayout: server.saveLayout });
    await advance(0);
    expect(region("Main")).toBeInTheDocument();
    expect(panelOrder()).toEqual(THREE);
    expect(screen.getByTestId("layout-notice")).toHaveTextContent("The saved layout could not be loaded");
    expect(screen.getByTestId("move-later-BTC")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByTestId("move-to-group-BTC")).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(screen.getByTestId("move-later-BTC"));
    expect(server.saveLayout).not.toHaveBeenCalled();

    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry loading the layout" }));
    await advance(0);
    expect(screen.getByTestId("layout-notice").textContent).toBe("");
    expect(screen.getByTestId("move-later-BTC")).not.toHaveAttribute("aria-disabled");
  });

  it("a recovered layout file shows its own notice", async () => {
    const server = layoutServer(layout([g("main", "Main", [])], { source: "recovered", revision: 0 }));
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout: server.fetchLayout, saveLayout: server.saveLayout });
    await advance(0);
    expect(screen.getByTestId("layout-notice")).toHaveTextContent("The saved layout file was unreadable");
    expect(panelOrder()).toEqual(THREE);
  });

  it("move earlier saves with the current revision, reorders, announces, refocuses and keeps the shared zoom", async () => {
    const server = layoutServer(layout([g("main", "Main", THREE)]));
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout: server.fetchLayout, saveLayout: server.saveLayout });
    await advance(0);
    zoomFrom("BTC", RANGE);
    const button = screen.getByTestId("move-earlier-ETH");
    button.focus();
    fireEvent.click(button);
    await advance(0);
    expect(server.saveLayout).toHaveBeenCalledWith({ revision: 3, groups: [g("main", "Main", ["ETH", "BTC", "SOL"])], hidden_lines: [] });
    expect(panelOrder()).toEqual(["ETH", "BTC", "SOL"]);
    expect(screen.getByTestId("board-announcer")).toHaveTextContent("ETH moved earlier in Main, now 1 of 3.");
    expect(document.activeElement).toBe(screen.getByTestId("move-earlier-ETH"));
    for (const s of THREE) expect(panelProps(s).linkedRange).toEqual(RANGE);

    // The next save carries the revision the last one returned.
    fireEvent.click(screen.getByTestId("move-later-BTC"));
    await advance(0);
    expect(server.saveLayout.mock.calls[1][0].revision).toBe(4);
  });

  it("a failed save rolls the order back and shows layout-save-error", async () => {
    const server = layoutServer(layout([g("main", "Main", THREE)]));
    const saveLayout = vi.fn(async () => Promise.reject(new Error("API request failed: /api/layout/crypto -> 500")));
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout: server.fetchLayout, saveLayout });
    await advance(0);
    fireEvent.click(screen.getByTestId("move-later-BTC"));
    await advance(0);
    expect(saveLayout).toHaveBeenCalledTimes(1);
    expect(panelOrder()).toEqual(THREE);
    expect(screen.getByTestId("layout-save-error")).toHaveTextContent("The layout was not saved");
  });

  it("a 409 reloads the layout and says it changed elsewhere", async () => {
    const server = layoutServer(layout([g("main", "Main", THREE)]));
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout: server.fetchLayout, saveLayout: server.saveLayout });
    await advance(0);
    server.set(layout([g("main", "Main", ["SOL", "ETH", "BTC"])], { revision: 7 }));
    fireEvent.click(screen.getByTestId("move-later-BTC"));
    await advance(0);
    expect(server.fetchLayout).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("layout-notice")).toHaveTextContent("Layout changed elsewhere; reloaded.");
    expect(panelOrder()).toEqual(["SOL", "ETH", "BTC"]);
  });

  it("creates, renames (with a validation message) and deletes a group", async () => {
    const server = layoutServer(layout([g("main", "Main", THREE)]));
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout: server.fetchLayout, saveLayout: server.saveLayout });
    await advance(0);

    fireEvent.click(screen.getByRole("button", { name: "New group" }));
    const input = screen.getByLabelText("New group name");
    fireEvent.change(input, { target: { value: "Watch" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await advance(0);
    expect(region("Watch")).toBeInTheDocument();
    const created = server.get().groups[1];
    expect(created.name).toBe("Watch");

    fireEvent.click(screen.getByRole("button", { name: "Rename group Watch" }));
    const rename = screen.getByLabelText("New name for group Watch");
    fireEvent.change(rename, { target: { value: "main" } });
    fireEvent.keyDown(rename, { key: "Enter" });
    expect(within(region("Watch")).getByRole("alert")).toHaveTextContent("A group with that name already exists.");
    fireEvent.change(rename, { target: { value: "Later" } });
    fireEvent.keyDown(rename, { key: "Enter" });
    await advance(0);
    expect(region("Later")).toBeInTheDocument();
    expect(server.get().groups[1].name).toBe("Later");

    fireEvent.change(screen.getByTestId("move-to-group-SOL"), { target: { value: created.id } });
    await advance(0);
    fireEvent.click(screen.getByRole("button", { name: "Delete group Later" }));
    await advance(0);
    expect(screen.queryByRole("region", { name: "Later" })).toBeNull();
    expect(server.get().groups).toEqual([g("main", "Main", THREE)]);
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Main" }));
  });

  it("the group menu moves a coin, saves, refocuses the menu and the moved chart starts at the shared zoom", async () => {
    const server = layoutServer(layout([g("main", "Main", ["BTC", "ETH"]), g("alts", "Alts", ["SOL"])]));
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout: server.fetchLayout, saveLayout: server.saveLayout });
    await advance(0);
    zoomFrom("SOL", RANGE);
    const mountsBefore = island.mounts.length;
    fireEvent.change(screen.getByTestId("move-to-group-ETH"), { target: { value: "alts" } });
    await advance(0);
    expect(server.get().groups).toEqual([g("main", "Main", ["BTC"]), g("alts", "Alts", ["SOL", "ETH"])]);
    expect(within(region("Alts")).getByTestId("coin-panel-ETH")).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByTestId("move-to-group-ETH"));
    expect(screen.getByTestId("board-announcer")).toHaveTextContent("ETH moved to Alts.");
    const moved = island.mounts.slice(mountsBefore).find((m) => m.target.closest('[data-testid="coin-panel-ETH"]'));
    expect((moved?.props as SimpleLinesProps).linkedRange).toEqual(RANGE);
  });

  it("remove after Confirm and add both refetch the board, the layout and the spaghetti chart; remove closes that coin's drill-down", async () => {
    const server = layoutServer(layout([g("main", "Main", THREE)]));
    let symbols = THREE;
    const fetchBoard = vi.fn(async (tf: Timeframe) => board(tf, symbols));
    const removeCoin = vi.fn(async (s: string) => {
      symbols = symbols.filter((x) => x !== s);
      return { coins: symbols };
    });
    const addCoin = vi.fn(async (s: string) => {
      symbols = [...symbols, s];
      return { coins: symbols };
    });
    const { fetchSpaghetti } = setup({ fetchBoard, fetchLayout: server.fetchLayout, saveLayout: server.saveLayout, removeCoin, addCoin });
    await advance(0);
    zoomFrom("BTC", RANGE);
    fireEvent.click(screen.getByTestId("open-drilldown-ETH"));
    await advance(0);
    expect(screen.getByTestId("drilldown-view")).toBeInTheDocument();

    const boards = fetchBoard.mock.calls.length;
    fireEvent.click(screen.getByTestId("remove-ETH"));
    fireEvent.click(screen.getByTestId("confirm-remove-ETH"));
    await advance(0);
    expect(removeCoin).toHaveBeenCalledWith("ETH");
    expect(fetchBoard).toHaveBeenCalledTimes(boards + 1);
    expect(server.fetchLayout).toHaveBeenCalledTimes(2);
    expect(fetchSpaghetti).toHaveBeenCalledTimes(2);
    expect(panelOrder()).toEqual(["BTC", "SOL"]);
    expect(screen.queryByTestId("drilldown-view")).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Main" }));
    expect(screen.getByTestId("coin-count")).toHaveTextContent("2 / 30 coins");
    for (const s of ["BTC", "SOL"]) expect(panelProps(s).linkedRange).toEqual(RANGE);

    fireEvent.change(screen.getByLabelText("Coin symbol"), { target: { value: "ada" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Add coin" }));
    });
    await advance(0);
    expect(addCoin).toHaveBeenCalledWith("ADA", "main");
    expect(fetchBoard).toHaveBeenCalledTimes(boards + 2);
    expect(server.fetchLayout).toHaveBeenCalledTimes(3);
    expect(fetchSpaghetti).toHaveBeenCalledTimes(3);
    expect(panelOrder()).toEqual(["BTC", "SOL", "ADA"]);
    expect(screen.getByTestId("coin-count")).toHaveTextContent("3 / 30 coins");
    expect(panelProps("ADA").linkedRange).toEqual(RANGE);
  });

  it("while an added coin's chart is unavailable the board is refetched at 4 s and 12 s, then no timer is left", async () => {
    const server = layoutServer(layout([g("main", "Main", THREE)]));
    let symbols = THREE;
    const fetchBoard = vi.fn(async (tf: Timeframe) => board(tf, symbols, ["NEW"]));
    const addCoin = vi.fn(async (s: string) => {
      symbols = [...symbols, s];
      return { coins: symbols };
    });
    setup({ fetchBoard, fetchLayout: server.fetchLayout, saveLayout: server.saveLayout, addCoin });
    await advance(0);
    expect(vi.getTimerCount()).toBe(0);
    fireEvent.change(screen.getByLabelText("Coin symbol"), { target: { value: "NEW" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Add coin" }));
    });
    await advance(0);
    const afterAdd = fetchBoard.mock.calls.length;
    await advance(3_999);
    expect(fetchBoard).toHaveBeenCalledTimes(afterAdd);
    await advance(1);
    expect(fetchBoard).toHaveBeenCalledTimes(afterAdd + 1);
    await advance(8_000);
    expect(fetchBoard).toHaveBeenCalledTimes(afterAdd + 2);
    await advance(60_000);
    expect(fetchBoard).toHaveBeenCalledTimes(afterAdd + 2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("the initial hidden lines come from the layout and a toggle saves hidden_lines", async () => {
    const server = layoutServer(layout([g("main", "Main", THREE)], { hidden_lines: ["ETH"] }));
    setup({ fetchBoard: async (tf) => board(tf, THREE), fetchLayout: server.fetchLayout, saveLayout: server.saveLayout });
    await advance(0);
    expect(screen.getByTestId("coin-count")).toHaveTextContent("3 / 30 coins");
    const toggle = screen.getByTestId("spaghetti-toggle-ETH");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    await advance(0);
    expect(server.saveLayout).toHaveBeenCalledWith({ revision: 3, groups: [g("main", "Main", THREE)], hidden_lines: [] });
    expect(screen.getByTestId("spaghetti-toggle-ETH")).toHaveAttribute("aria-pressed", "true");
  });

  it("an empty watchlist shows board-empty and the add form", async () => {
    const server = layoutServer(layout([g("main", "Main", [])]));
    setup({ fetchBoard: async (tf) => board(tf, []), fetchLayout: server.fetchLayout, saveLayout: server.saveLayout });
    await advance(0);
    expect(screen.getByTestId("board-empty")).toBeInTheDocument();
    expect(screen.getByLabelText("Coin symbol")).toBeInTheDocument();
    expect(screen.getByTestId("coin-count")).toHaveTextContent("0 / 30 coins");
  });

  it("a first board failure shows board-error and no groups; a later failure keeps the groups until the next success", async () => {
    const server = layoutServer(layout([g("main", "Main", THREE)]));
    let fail = true;
    setup({
      provider: true,
      fetchBoard: async (tf) => {
        if (fail) throw new Error("API request failed: board -> 503");
        return board(tf, THREE);
      },
      fetchLayout: server.fetchLayout,
      saveLayout: server.saveLayout,
    });
    await advance(0);
    expect(screen.getByTestId("board-error")).toHaveTextContent("503");
    expect(screen.queryByRole("region", { name: "Main" })).toBeNull();
    expect(screen.queryByTestId("board-loading")).toBeNull();

    fail = false;
    await advance(60_000);
    expect(screen.queryByTestId("board-error")).toBeNull();
    expect(panelOrder()).toEqual(THREE);

    fail = true;
    await advance(60_000);
    expect(screen.getByTestId("board-error")).toHaveTextContent("503");
    expect(region("Main")).toBeInTheDocument();
    expect(panelOrder()).toEqual(THREE);
  });
});
