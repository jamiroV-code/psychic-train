"use client";

import { useEffect, useRef, useState } from "react";
import { useLiveClock, useLiveStatus } from "@/components/screener/LiveProvider";
import type { LiveStatus } from "@/lib/live-poll";
import { announcement, stripModel, type StripModel, type StripState } from "@/lib/refresh-strip";

/** A strip model may add the latest bar line (T50 / S9E, equities). */
export type FreshnessModel = (status: LiveStatus, nowMs: number | null) => StripModel & { lastBar?: string | null };

/**
 * T43 / S11b: when the server last refreshed, when it refreshes next and when
 * this page last heard from it, in Brussels time by the server's clock. The
 * container has no heading and no `aria-live`; a visually hidden polite
 * status speaks only when the state changes (overdue, a failed check, and
 * the way back), never on a routine poll. Height is reserved from the first
 * render so the page below does not jump.
 *
 * T50 / S9E: `model` swaps the words (default `stripModel`, the crypto
 * strip); the equities page passes its own, which adds the latest bar line.
 */
export function FreshnessStrip({ model: buildModel = stripModel }: { model?: FreshnessModel } = {}) {
  const status = useLiveStatus();
  const nowMs = useLiveClock();
  const model = buildModel(status, nowMs);

  const [announced, setAnnounced] = useState("");
  const prevState = useRef<StripState | null>(null);
  useEffect(() => {
    const message = announcement(prevState.current, model.state);
    prevState.current = model.state;
    if (message !== null) setAnnounced(message);
  }, [model.state]);

  return (
    <section aria-label="Data freshness" data-testid="freshness-strip" className="freshness-strip">
      <div className="freshness-strip__items">
        {model.checking && <span className="freshness-strip__item">{model.checking}</span>}
        {model.off && <span className="freshness-strip__item">{model.off}</span>}
        {model.first && <span className="freshness-strip__item">{model.first}</span>}
        {model.lastBar && (
          <span className="freshness-strip__item" data-testid="strip-last-bar">
            {model.lastBar}
          </span>
        )}
        {model.refreshed && (
          <span className="freshness-strip__item" data-testid="strip-refreshed">
            {model.refreshed}
          </span>
        )}
        {model.next && (
          <span className="freshness-strip__item" data-testid="strip-next">
            {model.next}
          </span>
        )}
        {model.checked && (
          <span className="freshness-strip__item" data-testid="strip-checked">
            {model.checked}
          </span>
        )}
        {model.overdue && (
          <span className="freshness-strip__item freshness-strip__overdue" data-testid="strip-overdue">
            {model.overdue}
          </span>
        )}
        {model.notes.map((note) => (
          <span key={note} className="freshness-strip__item">
            {note}
          </span>
        ))}
      </div>
      {model.failed && (
        <p className="freshness-strip__failed" data-testid="strip-failed">
          {model.failed}
        </p>
      )}
      {model.zone && (
        <p className="freshness-strip__zone" data-testid="strip-zone">
          {model.zone}
        </p>
      )}
      <p className="freshness-strip__help" data-testid="strip-help">
        {model.help}
      </p>
      <div role="status" aria-live="polite" className="visually-hidden" data-testid="strip-announcer">
        {announced}
      </div>
    </section>
  );
}
