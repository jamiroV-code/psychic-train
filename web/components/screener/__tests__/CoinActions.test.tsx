import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CoinActions, type CoinActionsProps } from "@/components/screener/CoinActions";

const GROUPS = [
  { id: "main", name: "Main" },
  { id: "alts", name: "Alts" },
];

function setup(overrides: Partial<CoinActionsProps> = {}) {
  const props: CoinActionsProps = {
    symbol: "ETH",
    groupId: "main",
    groupName: "Main",
    groups: GROUPS,
    isFirst: false,
    isLast: false,
    onMove: vi.fn(),
    onMoveToGroup: vi.fn(),
    onRemove: vi.fn(),
    ...overrides,
  };
  render(<CoinActions {...props} />);
  return props;
}

describe("CoinActions", () => {
  it("every control is named after the coin and its group", () => {
    setup();
    expect(screen.getByRole("button", { name: "Move ETH earlier in Main" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Move ETH later in Main" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Move ETH from Main to group" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove ETH from Main" })).toBeInTheDocument();
  });

  it("edge buttons are aria-disabled, stay focusable and do nothing on click", () => {
    const props = setup({ isFirst: true, isLast: true });
    const earlier = screen.getByTestId("move-earlier-ETH");
    const later = screen.getByTestId("move-later-ETH");
    expect(earlier).toHaveAttribute("aria-disabled", "true");
    expect(later).toHaveAttribute("aria-disabled", "true");
    expect(earlier).not.toBeDisabled();
    fireEvent.click(earlier);
    fireEvent.click(later);
    expect(props.onMove).not.toHaveBeenCalled();
  });

  it("the move buttons call onMove with -1 and 1", () => {
    const props = setup();
    fireEvent.click(screen.getByTestId("move-earlier-ETH"));
    fireEvent.click(screen.getByTestId("move-later-ETH"));
    expect(props.onMove).toHaveBeenNthCalledWith(1, -1);
    expect(props.onMove).toHaveBeenNthCalledWith(2, 1);
  });

  it("the group menu lists every group and a change calls onMoveToGroup", () => {
    const props = setup();
    const select = screen.getByTestId("move-to-group-ETH") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.textContent)).toEqual(["Main", "Alts"]);
    expect(select.value).toBe("main");
    fireEvent.change(select, { target: { value: "alts" } });
    expect(props.onMoveToGroup).toHaveBeenCalledWith("alts");
  });

  it("only Confirm calls onRemove", () => {
    const props = setup();
    fireEvent.click(screen.getByTestId("remove-ETH"));
    expect(props.onRemove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel removing ETH" }));
    expect(props.onRemove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("remove-ETH"));
    fireEvent.click(screen.getByRole("button", { name: "Confirm removing ETH from Main" }));
    expect(props.onRemove).toHaveBeenCalledTimes(1);
  });

  it("Escape cancels the confirm and puts focus back on Remove", () => {
    const props = setup();
    fireEvent.click(screen.getByTestId("remove-ETH"));
    const confirm = screen.getByTestId("confirm-remove-ETH");
    expect(document.activeElement).toBe(confirm);
    fireEvent.keyDown(confirm, { key: "Escape" });
    expect(screen.queryByTestId("confirm-remove-ETH")).toBeNull();
    expect(document.activeElement).toBe(screen.getByTestId("remove-ETH"));
    expect(props.onRemove).not.toHaveBeenCalled();
  });

  it("buttons are native, so Enter and Space click them", async () => {
    const user = userEvent.setup();
    const props = setup();
    for (const el of screen.getAllByRole("button")) expect(el.tagName).toBe("BUTTON");
    screen.getByTestId("move-earlier-ETH").focus();
    await user.keyboard("{Enter}");
    screen.getByTestId("move-later-ETH").focus();
    await user.keyboard(" ");
    expect(props.onMove).toHaveBeenNthCalledWith(1, -1);
    expect(props.onMove).toHaveBeenNthCalledWith(2, 1);
  });
});
