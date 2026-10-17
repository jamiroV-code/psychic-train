"use client";

import { useEffect, useState } from "react";
import { DiscoveryTable } from "@/components/narrative/DiscoveryTable";
import { fetchDiscovery as fetchDiscoveryDefault } from "@/lib/api/discovery";
import type { DiscoveryReason, DiscoveryResponse, DiscoveryWindow } from "@/lib/types/discovery";

export interface DiscoveryTabProps {
  fetchDiscovery?: (window: DiscoveryWindow) => Promise<DiscoveryResponse>;
}

const WINDOWS: readonly DiscoveryWindow[] = [7, 30, 90];

const NO_DATA_LINES: Record<Exclude<DiscoveryReason, "">, string> = {
  "categories-missing": "Category lists have not been downloaded yet, so there is nothing to rank.",
  "reference-missing": "The reference data for this window is not available yet.",
  "no-attention-data": "There is no attention data to compare for this window yet.",
};

/** Discovery tab: 7d/30d/90d selector, then a ranked category table or one plain state line. */
export function DiscoveryTab({ fetchDiscovery = fetchDiscoveryDefault }: DiscoveryTabProps) {
  const [window, setWindow] = useState<DiscoveryWindow>(30);
  const [attempt, setAttempt] = useState(0);
  const [data, setData] = useState<DiscoveryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    fetchDiscovery(window)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
    // fetchDiscovery is a stable default or an injected test double.
  }, [window, attempt]);

  let body;
  if (error !== null) {
    body = (
      <div data-testid="discovery-error" role="alert">
        <p className="basket-note basket-note--error">Discovery could not be loaded.</p>
        <button type="button" className="board-button" data-testid="discovery-retry" onClick={() => setAttempt((n) => n + 1)}>
          Retry
        </button>
      </div>
    );
  } else if (data === null) {
    body = (
      <p data-testid="discovery-loading" className="basket-note" aria-busy="true">
        Loading discovery...
      </p>
    );
  } else if (data.status === "no-data") {
    const reason = data.reason === "" ? "no-attention-data" : data.reason;
    body = (
      <p data-testid={`discovery-nodata-${reason}`} className="basket-note">
        {NO_DATA_LINES[reason]}
      </p>
    );
  } else {
    body = <DiscoveryTable categories={data.categories} />;
  }

  return (
    <section data-testid="discovery-tab" aria-label="Category discovery" className="basket-chart">
      <header className="basket-chart__head">
        <h2 className="basket-chart__title">Attention by category</h2>
        <span className="basket-seg" role="group" aria-label="Window">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              className="basket-seg__btn"
              data-testid={`discovery-window-${w}`}
              aria-pressed={window === w}
              onClick={() => setWindow(w)}
            >
              {`${w}d`}
            </button>
          ))}
        </span>
      </header>
      {data && data.status === "ok" && (
        <p data-testid="discovery-as-of" className="basket-note">{`as of ${data.as_of.slice(0, 10)}`}</p>
      )}
      {body}
    </section>
  );
}
