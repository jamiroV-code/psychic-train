import { describe, expect, it } from "vitest";
import {
  addGroup,
  arrange,
  CAP_MESSAGE,
  deleteGroup,
  isFull,
  MAX_COINS,
  moveCoin,
  moveCoinToGroup,
  moveGroup,
  renameGroup,
  toggleLine,
} from "@/lib/layout-state";
import type { LayoutGroup } from "@/lib/types/layout";

function g(id: string, name: string, coins: string[]): LayoutGroup {
  return { id, name, coins };
}

const TWO = [g("main", "Main", ["BTC", "ETH"]), g("alts", "Alts", ["SOL", "ADA"])];

function fixedId(id: string) {
  return () => id;
}

describe("layout-state", () => {
  it("arrange drops symbols not on the board and appends unplaced coins to the last group", () => {
    const out = arrange(TWO, ["ADA", "BTC", "DOGE", "SOL"]);
    expect(out).toEqual([g("main", "Main", ["BTC"]), g("alts", "Alts", ["SOL", "ADA", "DOGE"])]);
  });

  it("arrange makes a Main group when the layout has no group", () => {
    expect(arrange([], ["BTC", "ETH"])).toEqual([g("main", "Main", ["BTC", "ETH"])]);
  });

  it("moves a coin one place earlier or later inside its group", () => {
    expect(moveCoin(TWO, "ETH", -1)[0].coins).toEqual(["ETH", "BTC"]);
    expect(moveCoin(TWO, "SOL", 1)[1].coins).toEqual(["ADA", "SOL"]);
  });

  it("an edge move is a no-op that returns the same groups", () => {
    expect(moveCoin(TWO, "BTC", -1)).toBe(TWO);
    expect(moveCoin(TWO, "ADA", 1)).toBe(TWO);
  });

  it("moves a coin to the end of another group", () => {
    const out = moveCoinToGroup(TWO, "BTC", "alts");
    expect(out).toEqual([g("main", "Main", ["ETH"]), g("alts", "Alts", ["SOL", "ADA", "BTC"])]);
  });

  it("adds a trimmed group and rejects empty, duplicate in any case, a 13th and a 41-character name", () => {
    const added = addGroup(TWO, "  Watch  ", fixedId("g-1"));
    expect(added).toEqual({ ok: true, id: "g-1", groups: [...TWO, g("g-1", "Watch", [])] });
    expect(addGroup(TWO, "   ").ok).toBe(false);
    expect(addGroup(TWO, "aLtS").ok).toBe(false);
    expect(addGroup(TWO, "x".repeat(41)).ok).toBe(false);
    const twelve = Array.from({ length: 12 }, (_, i) => g(`g${i}`, `G${i}`, []));
    expect(addGroup(twelve, "More").ok).toBe(false);
  });

  it("renames a group and keeps the same name check", () => {
    const out = renameGroup(TWO, "alts", " Others ");
    expect(out.ok && out.groups[1]).toEqual(g("alts", "Others", ["SOL", "ADA"]));
    expect(renameGroup(TWO, "alts", "MAIN").ok).toBe(false);
    expect(renameGroup(TWO, "alts", "alts").ok).toBe(true);
  });

  it("deleting a group moves its coins to the previous group, or the next one when it is first", () => {
    const later = deleteGroup(TWO, "alts");
    expect(later.groups).toEqual([g("main", "Main", ["BTC", "ETH", "SOL", "ADA"])]);
    expect(later.receiverId).toBe("main");
    const first = deleteGroup(TWO, "main");
    expect(first.groups).toEqual([g("alts", "Alts", ["SOL", "ADA", "BTC", "ETH"])]);
    expect(first.receiverId).toBe("alts");
  });

  it("the last group cannot be deleted", () => {
    const one = [g("main", "Main", ["BTC"])];
    const out = deleteGroup(one, "main");
    expect(out.groups).toBe(one);
    expect(out.receiverId).toBeNull();
  });

  it("moving a group clamps at both ends", () => {
    expect(moveGroup(TWO, "alts", -1).map((x) => x.id)).toEqual(["alts", "main"]);
    expect(moveGroup(TWO, "main", -1)).toBe(TWO);
    expect(moveGroup(TWO, "alts", 1)).toBe(TWO);
  });

  it("toggling a line adds or removes it from the hidden list", () => {
    expect(toggleLine(["BTC"], "ETH")).toEqual(["BTC", "ETH"]);
    expect(toggleLine(["BTC", "ETH"], "BTC")).toEqual(["ETH"]);
  });

  it("is full at 30 coins and over, with the exact cap message", () => {
    expect(MAX_COINS).toBe(30);
    expect(isFull(29)).toBe(false);
    expect(isFull(30)).toBe(true);
    expect(isFull(31)).toBe(true);
    expect(CAP_MESSAGE).toBe("Screener is full: 30 coins maximum. Remove a coin to add another.");
  });
});
