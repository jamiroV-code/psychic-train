// Mirrors api/models/layout.py (T40 / S5a). Keep in lockstep by hand;
// api/tests/routers/test_layout.py cross-checks the field names and types.
// Membership stays in the watchlist; a layout only groups and orders it.

// "file": read from layout.json; "default": nothing saved yet;
// "recovered": the stored file was unreadable and the default stands in.
export type LayoutSource = "file" | "default" | "recovered";

export interface LayoutGroup {
  id: string;
  name: string;
  coins: string[];
}

// `saved_at` is ISO-8601 UTC with a trailing "Z", null until a save.
export interface Layout {
  version: number;
  section: string;
  revision: number;
  saved_at: string | null;
  source: LayoutSource;
  groups: LayoutGroup[];
  hidden_lines: string[];
}

// `revision` must equal the stored one (0 for the default), else 409.
export interface LayoutUpdate {
  revision: number;
  groups: LayoutGroup[];
  hidden_lines: string[];
}
