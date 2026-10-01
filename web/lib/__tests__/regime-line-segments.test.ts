import { describe, expect, it } from "vitest";
import { lineBreakIndices } from "@/lib/regime-line-segments";

describe("lineBreakIndices", () => {
  it("returns flagged points that have an earlier real point", () => {
    expect(lineBreakIndices([1, null, 3, 4], [false, false, true, false])).toEqual([2]);
  });
  it("ignores a flag on the first real point and on whitespace", () => {
    expect(lineBreakIndices([null, 2, null, 4], [true, true, true, false])).toEqual([]);
  });
  it("is empty without flags", () => {
    expect(lineBreakIndices([1, 2, 3])).toEqual([]);
  });
});
