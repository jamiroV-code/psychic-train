"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { LayoutConflictError } from "@/lib/api/layout";
import { shareStructure } from "@/lib/same-data";
import type { Layout, LayoutGroup, LayoutUpdate } from "@/lib/types/layout";

/**
 * T41 / S5b: the screener layout as the board shows it.
 *
 * Loads once (and again on `reload` after an add or remove, or `retry`
 * after a failed load). An edit (`commit`) shows at once and is saved in a
 * serial queue; each save carries the revision the previous one returned. A
 * failed save rolls back to the last saved layout and says so in
 * `saveError`; a 409 reloads the layout and says it changed elsewhere. A
 * failed load leaves `layout` null and `status` "failed": the board shows
 * its default group and turns editing off. Answers after unmount are dropped
 * and nothing queued runs any more.
 */

export type LayoutStatus = "loading" | "ready" | "failed";

export const LOAD_FAILED_NOTICE =
  "The saved layout could not be loaded; showing the default order. Editing is off until it loads.";
export const RECOVERED_NOTICE =
  "The saved layout file was unreadable; the default layout is shown and the next change saves a new one.";
export const CONFLICT_NOTICE = "Layout changed elsewhere; reloaded.";

// Fields a save restamps; equal groups and hidden lines keep their objects.
const RESTAMPED = ["revision", "saved_at", "source", "version", "section"];

export interface BoardLayout {
  layout: Layout | null;
  status: LayoutStatus;
  notice: string;
  saveError: string;
  announcement: string;
  announce: (text: string) => void;
  commit: (groups: LayoutGroup[], hidden: string[]) => void;
  reload: () => void;
  retry: () => void;
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function useBoardLayout(
  fetchLayout: () => Promise<Layout>,
  saveLayout: (update: LayoutUpdate) => Promise<Layout>,
): BoardLayout {
  const [layout, setLayout] = useState<Layout | null>(null);
  const [status, setStatus] = useState<LayoutStatus>("loading");
  const [notice, setNotice] = useState("");
  const [saveError, setSaveError] = useState("");
  const [announcement, setAnnouncement] = useState("");

  const alive = useRef(true);
  const shown = useRef<Layout | null>(null);
  const saved = useRef<Layout | null>(null);
  const statusRef = useRef<LayoutStatus>("loading");
  const queue = useRef<Promise<void>>(Promise.resolve());
  const pending = useRef(0);
  // Bumped by a failed save: edits queued behind it were rolled back too.
  const epoch = useRef(0);
  const io = useRef({ fetchLayout, saveLayout });
  io.current = { fetchLayout, saveLayout };

  const show = useCallback((next: Layout | null) => {
    const value = next && shown.current ? shareStructure(shown.current, next, RESTAMPED) : next;
    shown.current = value;
    setLayout(value);
  }, []);

  const setStatusBoth = useCallback((next: LayoutStatus) => {
    statusRef.current = next;
    setStatus(next);
  }, []);

  const enqueue = useCallback((job: () => Promise<void>) => {
    queue.current = queue.current.then(job, job);
  }, []);

  const load = useCallback(
    async (initial: boolean) => {
      try {
        const fresh = await io.current.fetchLayout();
        if (!alive.current) return;
        saved.current = fresh;
        show(fresh);
        if (statusRef.current !== "ready" || initial) setNotice(fresh.source === "recovered" ? RECOVERED_NOTICE : "");
        setStatusBoth("ready");
      } catch (err) {
        if (!alive.current) return;
        if (statusRef.current === "ready") setSaveError(`The layout could not be reloaded: ${message(err)}`);
        else {
          setStatusBoth("failed");
          setNotice(LOAD_FAILED_NOTICE);
        }
      }
    },
    [show, setStatusBoth],
  );

  useEffect(() => {
    alive.current = true;
    enqueue(() => load(true));
    return () => {
      alive.current = false;
      epoch.current += 1;
    };
  }, [enqueue, load]);

  const reload = useCallback(() => enqueue(() => load(false)), [enqueue, load]);

  const retry = useCallback(() => {
    setNotice("");
    enqueue(() => load(true));
  }, [enqueue, load]);

  const commit = useCallback(
    (groups: LayoutGroup[], hidden: string[]) => {
      const base = shown.current;
      if (statusRef.current !== "ready" || !base) return;
      const mine = epoch.current;
      show({ ...base, groups, hidden_lines: hidden });
      setSaveError("");
      pending.current += 1;
      enqueue(async () => {
        try {
          if (!alive.current || mine !== epoch.current || !saved.current) return;
          const result = await io.current.saveLayout({ revision: saved.current.revision, groups, hidden_lines: hidden });
          if (!alive.current) return;
          saved.current = result;
          // Take the server's copy only when no newer edit is waiting.
          if (pending.current === 1) show(result);
        } catch (err) {
          if (!alive.current) return;
          epoch.current += 1;
          if (err instanceof LayoutConflictError) {
            try {
              const fresh = await io.current.fetchLayout();
              if (!alive.current) return;
              saved.current = fresh;
              show(fresh);
              setNotice(CONFLICT_NOTICE);
              return;
            } catch (reloadErr) {
              if (!alive.current) return;
              err = reloadErr;
            }
          }
          show(saved.current);
          setSaveError(`The layout was not saved: ${message(err)}`);
        } finally {
          pending.current -= 1;
        }
      });
    },
    [enqueue, show],
  );

  const announce = useCallback((text: string) => setAnnouncement(text), []);

  return { layout, status, notice, saveError, announcement, announce, commit, reload, retry };
}
