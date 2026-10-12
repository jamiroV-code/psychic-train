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
