"use client";

import { useEffect, useState } from "react";
import { fetchOnboarding as readOnboarding } from "@/lib/api/discovery";
import type { OnboardingResponse } from "@/lib/types/discovery";

const SOURCE_LABELS = { wikipedia: "Wikipedia", trends: "Google Trends", reddit_x: "Reddit / X" } as const;

/** Local evidence only. Placement and mode changes remain owner file edits. */
export function NewCoinsPanel({ fetchOnboarding = readOnboarding }: {
  fetchOnboarding?: () => Promise<OnboardingResponse>;
}) {
  const [data, setData] = useState<OnboardingResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setData(null);
    setFailed(false);
    fetchOnboarding().then((value) => {
      if (!cancelled) setData(value);
    }).catch(() => {
      if (!cancelled) setFailed(true);
    });
    return () => { cancelled = true; };
  }, [fetchOnboarding, attempt]);

  if (failed) return <div role="alert"><p>New coins could not be loaded.</p>
    <button type="button" onClick={() => setAttempt((n) => n + 1)}>Retry</button></div>;
  if (!data) return <p role="status">Loading new coins…</p>;
  return <section aria-label="New coins" className="space-y-6 py-6">
    <header className="space-y-2">
      <h2 className="text-xl font-semibold">New coins</h2>
      {data.mode === "shadow" && <p data-testid="onboarding-shadow">shadow: the universe is not changed</p>}
      <p className="text-sm text-muted-foreground">{data.probation_days} snapshots in the top 100 to join.
        {" "}Exit after {data.exit_days} snapshots outside rank {data.exit_band_rank}.
        {data.as_of && <> Last snapshot: {data.as_of}.</>}</p>
    </header>
    {data.status !== "ok" ? <p data-testid="onboarding-unavailable">
      {data.status === "corrupt" ? "The onboarding ledger could not be read. Its stored file has been kept." : "No onboarding ledger yet. The next daily refresh will create it."}
    </p> : data.coins.length === 0 ? <p>No new coins to review.</p> :
      <ul className="divide-y divide-border">
        {data.coins.map((coin) => <li key={coin.symbol} className="space-y-3 py-5">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <h3 className="font-mono text-lg font-semibold">{coin.symbol}</h3>
            <span>{coin.state}</span>
            <span>{coin.days_in_top100} of {data.probation_days} snapshots in the top 100</span>
          </div>
          <p>Class: {coin.class.replace(/_/g, " ")} · {coin.class_source === "auto" ? "automatic" : "owner"}</p>
          {Object.keys(coin.class_evidence).length > 0 && <details>
            <summary>Class evidence</summary><pre className="whitespace-pre-wrap break-words text-sm">{JSON.stringify(coin.class_evidence, null, 2)}</pre>
          </details>}
          <dl className="space-y-2">
            {(Object.keys(SOURCE_LABELS) as (keyof typeof SOURCE_LABELS)[]).map((source) => <div key={source} className="flex flex-wrap gap-x-3">
              <dt className="font-medium">{SOURCE_LABELS[source]}</dt>
              <dd className="break-words">{coin.sources[source].value ?? `${coin.sources[source].state}: ${coin.sources[source].reason}`}</dd>
            </div>)}
          </dl>
          {coin.pending.length === 0 ? <p>Pending: none</p> : <div><p>Pending review</p><ul>
            {coin.pending.map((item) => <li key={item.source}>{item.source}: {item.reason}</li>)}
          </ul></div>}
          {coin.proposal.length > 0 && <div><p>Narrative proposals — owner placement only</p><ul>
            {coin.proposal.map((item) => <li key={`${item.narrative}-${item.category}`}>{item.narrative} · category: {item.category}</li>)}
          </ul></div>}
        </li>)}
      </ul>}
  </section>;
}
