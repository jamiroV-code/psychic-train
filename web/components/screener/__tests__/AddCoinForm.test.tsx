import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AddCoinForm, type AddCoinFormProps } from "@/components/screener/AddCoinForm";
import { InvalidSymbolError, WatchlistFullError } from "@/lib/api/watchlist";

const GROUPS = [
  { id: "main", name: "Main" },
  { id: "alts", name: "Alts" },
];

function setup(overrides: Partial<AddCoinFormProps> = {}) {
  const props: AddCoinFormProps = {
    count: 3,
    groups: GROUPS,
    addCoin: vi.fn(async () => ({ coins: [] })),
    onAdded: vi.fn(),
    ...overrides,
  };
  render(<AddCoinForm {...props} />);
  return props;
}

function type(value: string) {
  fireEvent.change(screen.getByLabelText("Coin symbol"), { target: { value } });
}

async function submit() {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Add coin" }));
  });
}

describe("AddCoinForm", () => {
  it("has a labelled input, a group menu defaulting to the last group, the button and the count", () => {
    setup();
    expect(screen.getByLabelText("Coin symbol").tagName).toBe("INPUT");
    expect((screen.getByLabelText("Add to group") as HTMLSelectElement).value).toBe("alts");
    expect(screen.getByRole("button", { name: "Add coin" })).toBeInTheDocument();
    expect(screen.getByTestId("coin-count")).toHaveTextContent("3 / 30 coins");
  });

  it("trims and upper-cases the symbol and sends the chosen group", async () => {
    const props = setup();
    type("  sol ");
    fireEvent.change(screen.getByLabelText("Add to group"), { target: { value: "main" } });
    await submit();
    expect(props.addCoin).toHaveBeenCalledWith("SOL", "main");
  });

  it("an empty symbol shows an inline error and sends nothing", async () => {
    const props = setup();
    type("   ");
    await submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a coin symbol.");
    expect(props.addCoin).not.toHaveBeenCalled();
  });

  it("at 30 coins the full message shows, the button is aria-disabled and a click sends nothing", async () => {
    const props = setup({ count: 30 });
    expect(screen.getByTestId("add-coin-full")).toHaveTextContent(
      "Screener is full: 30 coins maximum. Remove a coin to add another.",
    );
    const button = screen.getByRole("button", { name: "Add coin" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    type("SOL");
    await submit();
    expect(props.addCoin).not.toHaveBeenCalled();
    expect(screen.getByTestId("coin-count")).toHaveTextContent("30 / 30 coins");
  });

  it("a server 409 shows the server text as an alert", async () => {
    setup({ addCoin: vi.fn(async () => Promise.reject(new WatchlistFullError("server says full"))) });
    type("SOL");
    await submit();
    expect(screen.getByRole("alert")).toHaveTextContent("server says full");
  });

  it("a 422 says the symbol is not valid", async () => {
    setup({ addCoin: vi.fn(async () => Promise.reject(new InvalidSymbolError("invalid symbol"))) });
    type("$$");
    await submit();
    expect(screen.getByRole("alert")).toHaveTextContent("$$ is not a valid symbol.");
  });

  it("a network error says the coin could not be added", async () => {
    setup({ addCoin: vi.fn(async () => Promise.reject(new Error("Failed to fetch"))) });
    type("SOL");
    await submit();
    expect(screen.getByRole("alert")).toHaveTextContent("Could not add SOL: Failed to fetch");
  });

  it("success clears the input, keeps focus in it and calls onAdded", async () => {
    const props = setup();
    const input = screen.getByLabelText("Coin symbol") as HTMLInputElement;
    input.focus();
    type("sol");
    await act(async () => {
      fireEvent.submit(input.form!);
    });
    expect(props.onAdded).toHaveBeenCalledWith("SOL");
    expect(input.value).toBe("");
    expect(document.activeElement).toBe(input);
    expect(screen.getByRole("alert").textContent).toBe("");
  });

  it("a pending add blocks a second submit", async () => {
    let finish: (() => void) | null = null;
    const addCoin = vi.fn(
      () =>
        new Promise<{ coins: string[] }>((resolve) => {
          finish = () => resolve({ coins: [] });
        }),
    );
    setup({ addCoin });
    type("SOL");
    await submit();
    expect(screen.getByRole("button", { name: "Add coin" })).toHaveAttribute("aria-disabled", "true");
    await submit();
    expect(addCoin).toHaveBeenCalledTimes(1);
    await act(async () => {
      finish!();
    });
    expect(screen.getByRole("button", { name: "Add coin" })).not.toHaveAttribute("aria-disabled", "true");
  });
});

describe("AddCoinForm suggestions", () => {
  const result = (...symbols: string[]) =>
    Promise.resolve({
      ready: true,
      suggestions: symbols.map((symbol) => ({ symbol, name: `${symbol} name`, venues: ["Hyperliquid"] })),
    });

  it("asks again on every letter typed and lists name, symbol and venue", async () => {
    const suggest = vi.fn((_kind: string, q: string) => result(q.toUpperCase()));
    setup({ suggest });
    for (const text of ["s", "sh", "shi"]) {
      await act(async () => {
        type(text);
      });
    }
    expect(suggest.mock.calls.map((c) => [c[0], c[1]])).toEqual([
      ["coin", "s"],
      ["coin", "sh"],
      ["coin", "shi"],
    ]);
    const option = await screen.findByTestId("add-coin-suggestion");
    expect(option).toHaveTextContent("SHI");
    expect(option).toHaveTextContent("SHI name");
    expect(option).toHaveTextContent("Hyperliquid");
  });

  it("drops an answer that arrives after a newer keystroke", async () => {
    let resolveSlow: (v: unknown) => void = () => {};
    const slow = new Promise((r) => {
      resolveSlow = r;
    });
    const suggest = vi.fn((_kind: string, q: string, _s?: AbortSignal) => (q === "s" ? (slow as never) : result("SOL")));
    setup({ suggest });
    await act(async () => {
      type("s");
    });
    await act(async () => {
      type("so");
    });
    await act(async () => {
      resolveSlow({ ready: true, suggestions: [{ symbol: "STALE", name: "old", venues: [] }] });
    });
    expect(screen.queryByText("STALE")).toBeNull();
    expect(await screen.findByText("SOL")).toBeInTheDocument();
  });

  it("picking a suggestion fills the symbol, and Add sends it", async () => {
    const suggest = vi.fn(() => result("SHIB", "SHIBDOGE"));
    const props = setup({ suggest });
    await act(async () => {
      type("shi");
    });
    const options = await screen.findAllByTestId("add-coin-suggestion");
    fireEvent.mouseDown(options[1]);
    expect((screen.getByLabelText("Coin symbol") as HTMLInputElement).value).toBe("SHIBDOGE");
    expect(screen.queryByTestId("add-coin-suggestions")).toBeNull();
    await submit();
    expect(props.addCoin).toHaveBeenCalledWith("SHIBDOGE", "alts");
  });

  it("arrow keys move through the list, Enter picks, Escape closes", async () => {
    const suggest = vi.fn(() => result("AAA", "BBB"));
    setup({ suggest });
    const input = screen.getByLabelText("Coin symbol");
    await act(async () => {
      type("a");
    });
    await screen.findAllByTestId("add-coin-suggestion");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "Enter" });
    expect((input as HTMLInputElement).value).toBe("BBB");
    await act(async () => {
      type("b");
    });
    await screen.findAllByTestId("add-coin-suggestion");
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByTestId("add-coin-suggestions")).toBeNull();
  });

  it("a failing suggestion service never blocks typing a symbol and adding it", async () => {
    const suggest = vi.fn(() => Promise.reject(new Error("down")));
    const props = setup({ suggest });
    await act(async () => {
      type("sol");
    });
    expect(screen.queryByTestId("add-coin-suggestions")).toBeNull();
    await submit();
    expect(props.addCoin).toHaveBeenCalledWith("SOL", "alts");
  });

  it("says so when nothing matches or the index is still building, and clears when the box empties", async () => {
    const suggest = vi.fn((_k: string, q: string) =>
      Promise.resolve({ ready: q !== "zz", suggestions: [] }),
    );
    setup({ suggest });
    await act(async () => {
      type("qq");
    });
    expect(await screen.findByTestId("add-coin-no-match")).toHaveTextContent("No match.");
    await act(async () => {
      type("zz");
    });
    expect(await screen.findByTestId("add-coin-no-match")).toHaveTextContent("Still building");
    await act(async () => {
      type("");
    });
    expect(screen.queryByTestId("add-coin-suggestions")).toBeNull();
  });
});
